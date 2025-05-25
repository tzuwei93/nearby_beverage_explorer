#!/usr/bin/env python3
"""
Nearby Beverage Explorer - Main Script

This script serves as a local development entry point for the Nearby Beverage Explorer application.
The production version of this application runs on AWS Lambda with Step Functions,
but this script allows you to run the data collection process locally for testing.

For production deployment, use src/deploy.py to deploy the serverless infrastructure.
"""

import os
import argparse
import logging
import json
from datetime import datetime

# Import project modules
from src.config import logger
from lambda_functions.places_collector import GooglePlacesClient, LocalStorage, S3Storage, DataCollector


def display_serverless_info():
    """Display information about the serverless architecture"""
    logger.info("""
SERVERLESS ARCHITECTURE INFORMATION:

The Nearby Beverage Explorer application uses a serverless architecture on AWS:

1. DATA COLLECTION:
   - AWS Lambda function 'google_places_collector' fetches data from Google Places API
   - Triggered weekly by EventBridge scheduler (every Friday)
   - Results stored directly in S3

2. ORCHESTRATION:
   - AWS Step Functions state machine coordinates the data flow
   - Can be triggered manually or on schedule
   - Handles retries and error notification

3. DEPLOYMENT:
   - Use 'python -m src.deploy' to deploy the serverless infrastructure
   - CloudFormation template in src/cloudformation/serverless.yaml
   - Lambda code in src/lambda_functions/

For local testing, use this script with '--collect' to run the data collection locally.
For production, deploy the serverless infrastructure using the deploy script.
""")

def main():
    """Main function to run the application"""
    parser = argparse.ArgumentParser(description='Nearby Beverage Explorer (Local Development)')
    parser.add_argument('--info', action='store_true', help='Display serverless architecture information')
    
    args = parser.parse_args()
    
    # Default to showing info if no arguments provided
    if not (args.collect or args.process or args.info):
        args.info = True
    
    try:
        # Handle different operations
        if args.info:
            display_serverless_info()
        return 0
        
    except Exception as e:
        logger.error(f"Error in main script: {e}")
        return 1

if __name__ == '__main__':
    exit_code = main()
    exit(exit_code) 