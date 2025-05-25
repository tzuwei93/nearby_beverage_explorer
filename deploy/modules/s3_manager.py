"""S3 bucket management module"""

import os
import logging
import glob
from pathlib import Path
from .command_runner import CommandRunner

logger = logging.getLogger(__name__)

class S3Manager:
    """Manages S3 bucket operations"""
    
    def __init__(self, bucket_name, region):
        """Initialize S3Manager
        
        Args:
            bucket_name (str): Name of the S3 bucket
            region (str): AWS region
        """
        self.bucket_name = bucket_name
        self.region = region
        self.command_runner = CommandRunner()
    
    def bucket_exists(self):
        """Check if the S3 bucket exists
        
        Returns:
            bool: True if bucket exists, False otherwise
        """
        command = f"aws s3api head-bucket --bucket {self.bucket_name} --region {self.region}"
        return self.command_runner.run(command, check_success=False)
    
    def create_bucket(self):
        """Create an S3 bucket
        
        Returns:
            bool: True if creation was successful, False otherwise
        """
        # For regions other than us-east-1, we need to specify LocationConstraint
        if self.region != "us-east-1":
            command = (
                f"aws s3api create-bucket "
                f"--bucket {self.bucket_name} "
                f"--region {self.region} "
                f"--create-bucket-configuration LocationConstraint={self.region}"
            )
        else:
            command = (
                f"aws s3api create-bucket "
                f"--bucket {self.bucket_name} "
                f"--region {self.region}"
            )
        
        logger.info(f"Creating S3 bucket: {self.bucket_name}")
        return self.command_runner.run(command)
    
    def ensure_bucket(self):
        """Ensure the S3 bucket exists, creating it if necessary
        
        Returns:
            bool: True if bucket exists or was created successfully, False otherwise
        """
        if not self.bucket_exists():
            return self.create_bucket()
        return True
    
    def create_directory(self, directory_path):
        """Create a directory in the S3 bucket
        
        Args:
            directory_path (str): Directory path to create
            
        Returns:
            bool: True if directory was created successfully, False otherwise
        """
        # Ensure the path ends with a slash
        if not directory_path.endswith('/'):
            directory_path += '/'
            
        command = (
            f"aws s3api put-object "
            f"--bucket {self.bucket_name} "
            f"--key {directory_path} "
            f"--content-length 0"
        )
        
        logger.info(f"Creating directory in S3: s3://{self.bucket_name}/{directory_path}")
        return self.command_runner.run(command)
    
    def upload_file(self, local_file, s3_key):
        """Upload a file to the S3 bucket
        
        Args:
            local_file (str): Path to local file
            s3_key (str): S3 object key
            
        Returns:
            bool: True if upload was successful, False otherwise
        """
        command = (
            f"aws s3 cp {local_file} "
            f"s3://{self.bucket_name}/{s3_key} "
            f"--region {self.region}"
        )
        
        logger.info(f"Uploading file to S3: {local_file} -> s3://{self.bucket_name}/{s3_key}")
        return self.command_runner.run(command)
    
    def upload_directory(self, local_dir, s3_prefix, file_pattern="*"):
        """Upload all files in a directory to the S3 bucket
        
        Args:
            local_dir (str): Path to local directory
            s3_prefix (str): S3 prefix to upload files to
            file_pattern (str): File pattern to match (default: "*")
            
        Returns:
            bool: True if all uploads were successful, False otherwise
        """
        # Ensure the S3 prefix ends with a slash if it's not empty
        if s3_prefix and not s3_prefix.endswith('/'):
            s3_prefix += '/'
            
        # Create the directory in S3
        if s3_prefix:
            self.create_directory(s3_prefix)
        
        # Get all files matching the pattern
        local_dir_path = Path(local_dir)
        file_paths = list(local_dir_path.glob(file_pattern))
        
        success = True
        for file_path in file_paths:
            if file_path.is_file():
                relative_path = file_path.relative_to(local_dir_path)
                s3_key = f"{s3_prefix}{relative_path}"
                if not self.upload_file(str(file_path), s3_key):
                    success = False
        
        return success
