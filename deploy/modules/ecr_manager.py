"""ECR repository management module"""

import os
import logging
import boto3
from .command_runner import CommandRunner

logger = logging.getLogger(__name__)

class ECRManager:
    """Manages ECR repository operations"""
    
    def __init__(self, region, repository_name):
        self.region = region
        self.repository_name = repository_name
        self.ecr_client = boto3.client('ecr', region_name=region)
        self.command_runner = CommandRunner()
    
    def repository_exists(self):
        """Check if ECR repository exists"""
        try:
            self.ecr_client.describe_repositories(repositoryNames=[self.repository_name])
            return True
        except self.ecr_client.exceptions.RepositoryNotFoundException:
            return False
    
    def ensure_repository(self):
        """Ensure the ECR repository exists, create if it doesn't"""
        if not self.repository_exists():
            logger.info(f"Creating ECR repository {self.repository_name}")
            self.ecr_client.create_repository(
                repositoryName=self.repository_name,
                imageScanningConfiguration={'scanOnPush': True},
                imageTagMutability='MUTABLE'
            )
        
        account_id = boto3.client('sts').get_caller_identity()['Account']
        repository_uri = f"{account_id}.dkr.ecr.{self.region}.amazonaws.com/{self.repository_name}"
        return repository_uri
    
    def build_and_push_images(self, version, services):
        """Build and push Docker images to ECR for specified services"""
        logger.info(f"Building and pushing Docker images with version {version} for services: {', '.join(services)}...")
        script_path = "src/docker/build_and_push.sh"
        
        # Make script executable
        os.chmod(script_path, 0o755)
        
        for service in services:
            logger.info(f"Processing service: {service}")
            try:
                self.command_runner.run(
                    f"{script_path} --region {self.region} --repository {self.repository_name} --version {version} --service {service}"
                )
                logger.info(f"Successfully built and pushed Docker image for service {service}")
            except Exception as e:
                logger.error(f"Error building and pushing Docker image for service {service}: {str(e)}")
                raise
        logger.info("Successfully built and pushed all specified Docker images")