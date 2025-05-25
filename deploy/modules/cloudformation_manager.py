"""CloudFormation deployment management module"""

import logging
import json
import subprocess
import time
from .command_runner import CommandRunner

logger = logging.getLogger(__name__)

class CloudFormationManager:
    """Manages CloudFormation stack operations"""
    
    def __init__(self, stack_name, region):
        self.stack_name = stack_name
        self.region = region
        self.command_runner = CommandRunner()
    
    def _format_parameters(self, parameters):
        """Format parameters for AWS CLI
        
        Args:
            parameters (dict): Dictionary of parameter key-value pairs
            
        Returns:
            str: Formatted parameters string for AWS CLI
            
        Example:
            Input: {'AppName': 'my-app', 'Version': 'v1'}
            Output: 'ParameterKey=AppName,ParameterValue=my-app ParameterKey=Version,ParameterValue=v1'
        """
        return " ".join([
            f"ParameterKey={key},ParameterValue={value}"
            for key, value in parameters.items()
        ])
    
    def get_stack_status(self):
        """Get the current status of the CloudFormation stack
        
        Returns:
            str: Stack status if stack exists, None otherwise
        """
        command = (
            f"aws cloudformation describe-stacks "
            f"--stack-name {self.stack_name} "
            f"--region {self.region} "
            f"--query 'Stacks[0].StackStatus' "
            f"--output text"
        )
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=False,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None
    
    def delete_stack(self):
        """Delete the CloudFormation stack
        
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        command = (
            f"aws cloudformation delete-stack "
            f"--stack-name {self.stack_name} "
            f"--region {self.region}"
        )
        
        logger.info(f"Deleting stack: {self.stack_name}")
        if not self.command_runner.run(command):
            return False
            
        # Wait for stack deletion
        wait_command = (
            f"aws cloudformation wait stack-delete-complete "
            f"--stack-name {self.stack_name} "
            f"--region {self.region}"
        )
        
        logger.info("Waiting for stack deletion to complete...")
        return self.command_runner.run(wait_command, check_success=False)
    
    def stack_exists(self):
        """Check if the CloudFormation stack exists
        
        Returns:
            bool: True if stack exists, False otherwise
        """
        command = (
            f"aws cloudformation describe-stacks "
            f"--stack-name {self.stack_name} "
            f"--region {self.region}"
        )
        
        return self.command_runner.run(command, check_success=False)
    
    def create_stack(self, template_file, parameters):
        """Create a new CloudFormation stack
        
        Args:
            template_file (str): Path to CloudFormation template
            parameters (dict): Template parameters
        """
        params_str = self._format_parameters(parameters)
        
        command = (
            f"aws cloudformation create-stack "
            f"--stack-name {self.stack_name} "
            f"--template-body file://{template_file} "
            f"--parameters {params_str} "
            f"--capabilities CAPABILITY_IAM "
            f"--region {self.region}"
        )
        
        logger.info(f"Creating new stack: {self.stack_name}")
        if not self.command_runner.run(command):
            raise Exception("Failed to create stack")
            
        return self.wait_for_stack_creation()
    
    def wait_for_stack_creation(self):
        """Wait for stack creation to complete"""
        command = (
            f"aws cloudformation wait stack-create-complete "
            f"--stack-name {self.stack_name} "
            f"--region {self.region}"
        )
        
        logger.info("Waiting for stack creation to complete...")
        return self.command_runner.run(command)
    
    def create_change_set(self, template_file, parameters, version):
        """Create a CloudFormation change set
        
        Args:
            template_file (str): Path to CloudFormation template
            parameters (dict): Template parameters
            version (str): Version string for change set name
        """
        change_set_name = f"{self.stack_name}-change-{version}"
        params_str = self._format_parameters(parameters)
        
        command = (
            f"aws cloudformation create-change-set "
            f"--stack-name {self.stack_name} "
            f"--change-set-name {change_set_name} "
            f"--template-body file://{template_file} "
            f"--parameters {params_str} "
            f"--capabilities CAPABILITY_IAM "
            f"--region {self.region}"
        )
        
        logger.info(f"Creating change set: {change_set_name}")
        result = self.command_runner.run(command)
        return change_set_name if result else None
    
    def wait_for_change_set(self, change_set_name):
        """Wait for change set creation to complete
        
        Args:
            change_set_name (str): Name of the change set to wait for
        """
        command = (
            f"aws cloudformation wait change-set-create-complete "
            f"--stack-name {self.stack_name} "
            f"--change-set-name {change_set_name} "
            f"--region {self.region}"
        )
        
        logger.info(f"Waiting for change set {change_set_name} to be ready...")
        return self.command_runner.run(command)
    
    def execute_change_set(self, change_set_name):
        """Execute a CloudFormation change set
        
        Args:
            change_set_name (str): Name of the change set to execute
        """
        command = (
            f"aws cloudformation execute-change-set "
            f"--stack-name {self.stack_name} "
            f"--change-set-name {change_set_name} "
            f"--region {self.region}"
        )
        
        logger.info(f"Executing change set: {change_set_name}")
        return self.command_runner.run(command)
    
    def wait_for_stack_update(self):
        """Wait for stack update to complete"""
        command = (
            f"aws cloudformation wait stack-update-complete "
            f"--stack-name {self.stack_name} "
            f"--region {self.region}"
        )
        
        logger.info("Waiting for stack update to complete...")
        return self.command_runner.run(command)
    
    def deploy(self, template_file, parameters, version):
        """Deploy CloudFormation stack using change sets
        
        Args:
            template_file (str): Path to CloudFormation template
            parameters (dict): Template parameters
            version (str): Version string for change set name
        """
        # Check stack status
        if self.stack_exists():
            status = self.get_stack_status()
            logger.info(f"Current stack status: {status}")
            
            # If stack is in ROLLBACK_FAILED or other failed states, delete it
            if status and ('FAILED' in status or 'ROLLBACK' in status):
                logger.warning(f"Stack is in {status} state. Deleting stack before proceeding...")
                if not self.delete_stack():
                    raise Exception("Failed to delete failed stack")
                # Wait a bit for deletion to propagate
                time.sleep(5)
        
        # Create new stack if it doesn't exist
        if not self.stack_exists():
            logger.info(f"Stack {self.stack_name} does not exist, creating new stack...")
            return self.create_stack(template_file, parameters)
            
        # Update existing stack using change set
        logger.info(f"Updating existing stack {self.stack_name}...")
        
        # Create and wait for change set
        change_set_name = self.create_change_set(template_file, parameters, version)
        if not change_set_name:
            raise Exception("Failed to create change set")
            
        if not self.wait_for_change_set(change_set_name):
            raise Exception("Change set creation failed or timed out")
            
        # Execute change set and wait for stack update
        if not self.execute_change_set(change_set_name):
            raise Exception("Failed to execute change set")
            
        if not self.wait_for_stack_update():
            raise Exception("Stack update failed or timed out")
            
        logger.info("Stack deployment completed successfully") 