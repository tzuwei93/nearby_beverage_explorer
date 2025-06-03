#!/usr/bin/env python3
"""
Deployment script for Nearby Beverage    Explorer

This script deploys the CloudFormation stack for the Nearby Beverage Explorer application,
which uses container-based Lambda functions stored in Amazon ECR.
It supports nested CloudFormation stacks by uploading templates to S3.
"""

import os
import sys
import logging
import glob
import argparse
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Add the parent directory to sys.path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import (
    AWS_DEFAULT_REGION,
    S3_BUCKET_NAME,
    GOOGLE_MAPS_API_KEY,
    LOCATION_LAT,
    LOCATION_LNG,
    SEARCH_RADIUS_METERS,
    RAW_DATA_PREFIX,
    HUDI_DATA_PREFIX,
    ANALYTICS_DATA_PREFIX,
    STACK_NAME,
    TEMPLATE_DIR,
    MAIN_TEMPLATE_FILE,
    ECR_REPOSITORY_NAME,
    LAMBDA_SERVICES_TO_BUILD,
    CLOUDFORMATION_S3_PREFIX
)

from modules import (
    VersionManager,
    ECRManager,
    CloudFormationManager,
    S3Manager
)

def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Deploy Nearby Beverage Explorer CloudFormation stack')
    parser.add_argument('--latitude', type=float, help='Latitude for the location center point (e.g., 25.041171)')
    parser.add_argument('--longitude', type=float, help='Longitude for the location center point (e.g., 121.565227)')
    parser.add_argument('--radius', type=int, help='Search radius in meters (e.g., 5000)')
    return parser.parse_args()

def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def get_cloudformation_parameters(stack_name, repository_exists, version, args=None):
    """Get parameters for CloudFormation template
    
    Args:
        stack_name (str): Name of the CloudFormation stack
        repository_exists (bool): Whether the ECR repository already exists
        version (str): Version string for the deployment
        args (Namespace, optional): Command-line arguments. Defaults to None.
        
    Returns:
        dict: Parameters for the CloudFormation template
    """
    # Use command-line arguments if provided, otherwise use config values
    location_lat = str(args.latitude) if args and args.latitude is not None else str(LOCATION_LAT)
    location_lng = str(args.longitude) if args and args.longitude is not None else str(LOCATION_LNG)
    search_radius = str(args.radius) if args and args.radius is not None else str(SEARCH_RADIUS_METERS)
    
    return {
        'AppName': stack_name,
        'GoogleMapsApiKey': GOOGLE_MAPS_API_KEY,
        'LocationLat': location_lat,
        'LocationLng': location_lng,
        'SearchRadiusMeters': search_radius,
        'S3BucketName': S3_BUCKET_NAME,
        'ECRRepositoryName': ECR_REPOSITORY_NAME,
        'CreateECRRepository': str(not repository_exists).lower(),
        'Version': version,
        'RawDataPrefix': RAW_DATA_PREFIX,
        'HudiDataPrefix': HUDI_DATA_PREFIX,
        'AnalyticsDataPrefix': ANALYTICS_DATA_PREFIX
    }

def upload_nested_templates(s3_manager, logger):
    """Upload nested CloudFormation templates to S3
    
    Args:
        s3_manager (S3Manager): S3 manager instance
        logger (Logger): Logger instance
        
    Returns:
        bool: True if upload was successful, False otherwise
    """
    # Ensure S3 bucket exists
    if not s3_manager.ensure_bucket():
        logger.error(f"Failed to ensure S3 bucket: {s3_manager.bucket_name}")
        return False
    
    # Create cloudformation directory in S3 bucket
    if not s3_manager.create_directory(CLOUDFORMATION_S3_PREFIX):
        logger.error(f"Failed to create directory in S3: {CLOUDFORMATION_S3_PREFIX}")
        return False
    
    # Get all YAML files in the template directory
    template_dir = Path(TEMPLATE_DIR)
    template_files = list(template_dir.glob("*.yaml"))
    
    # Upload each template file to S3
    success = True
    for template_file in template_files:
        s3_key = f"{CLOUDFORMATION_S3_PREFIX}/{template_file.name}"
        if not s3_manager.upload_file(str(template_file), s3_key):
            logger.error(f"Failed to upload template: {template_file}")
            success = False
    
    return success

def main():
    """Main deployment function"""
    try:
        # Setup
        load_dotenv()
        logger = setup_logging()
        args = parse_arguments()
        version = VersionManager.generate_version()
        
        # Log deployment information
        logger.info(f"Starting deployment with version: {version}")
        if args.latitude is not None and args.longitude is not None:
            logger.info(f"Using custom location: ({args.latitude}, {args.longitude})")
        if args.radius is not None:
            logger.info(f"Using custom search radius: {args.radius} meters")
        
        # Initialize managers
        ecr = ECRManager(AWS_DEFAULT_REGION, ECR_REPOSITORY_NAME)
        s3 = S3Manager(S3_BUCKET_NAME, AWS_DEFAULT_REGION)
        cfn = CloudFormationManager(STACK_NAME, AWS_DEFAULT_REGION)
        
        # Handle ECR repository
        repository_exists = ecr.repository_exists()
        if not repository_exists:
            repository_uri = ecr.ensure_repository()
            logger.info(f"Created ECR repository: {repository_uri}")
            repository_exists = True
        else:
            logger.info(f"Using existing ECR repository: {ECR_REPOSITORY_NAME}")
        
        # Build and push Docker images
        ecr.build_and_push_images(version, LAMBDA_SERVICES_TO_BUILD)
            
        # Upload nested CloudFormation templates to S3
        logger.info("Uploading nested CloudFormation templates to S3...")
        if not upload_nested_templates(s3, logger):
            raise Exception("Failed to upload nested templates to S3")
        
        # Deploy CloudFormation stack
        parameters = get_cloudformation_parameters(STACK_NAME, repository_exists, version, args)
        cfn.deploy(MAIN_TEMPLATE_FILE, parameters, version.replace(".", "-") + "-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        
        logger.info(f"Deployment completed successfully with version {version}")
        
        # should consider to push the images to ECR after the cfn deployed
        
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()