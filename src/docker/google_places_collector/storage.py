#!/usr/bin/env python3
"""
Storage module for saving data to S3
"""

import json
import logging
import boto3
from typing import Any, Dict
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class S3Storage:
    """Storage class for saving data to S3"""
    
    def __init__(self, bucket: str, prefix: str = ""):
        """
        Initialize the storage
        
        Args:
            bucket: S3 bucket name
            prefix: Prefix for S3 keys (optional)
        """
        self.s3 = boto3.client('s3')
        self.bucket = bucket
        self.prefix = prefix.rstrip('/') + '/' if prefix else ""
    
    def save_data(self, data: Dict[str, Any], file_name: str) -> str:
        """
        Save data to S3
        
        Args:
            data: Data to save
            file_name: Name of the file
            
        Returns:
            S3 location of saved file
            
        Raises:
            Exception: If save fails
        """
        try:
            # Ensure the file name doesn't start with /
            file_name = file_name.lstrip('/')
            
            # Create the full S3 key
            s3_key = self.prefix + file_name
            
            # Convert data to JSON string
            json_data = json.dumps(data, indent=2)
            
            # Upload to S3
            self.s3.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )
            
            logger.info(f"Saved data to s3://{self.bucket}/{s3_key}")
            return f"s3://{self.bucket}/{s3_key}"
            
        except ClientError as e:
            logger.error(f"Error saving to S3: {str(e)}")
            raise Exception(f"Failed to save data to S3: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error saving to S3: {str(e)}")
            raise 