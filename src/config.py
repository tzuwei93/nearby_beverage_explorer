import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

# Google Places API configuration
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
if not GOOGLE_MAPS_API_KEY:
    logger.warning("GOOGLE_MAPS_API_KEY not found in environment variables")

# Location configuration
LOCATION_LAT = float(os.getenv('LOCATION_LAT', '25.041171'))
LOCATION_LNG = float(os.getenv('LOCATION_LNG', '121.565227'))
SEARCH_RADIUS_METERS = int(os.getenv('SEARCH_RADIUS_METERS', 5000))

# AWS configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'ap-southeast-1')

# Deployment configuration
STACK_NAME = os.getenv('STACK_NAME', 'nearby-beverage-explorer')
TEMPLATE_DIR = os.getenv('TEMPLATE_DIR', 'src/cloudformation')
MAIN_TEMPLATE_FILE = f"{TEMPLATE_DIR}/serverless.yaml"
ECR_REPOSITORY_NAME = os.getenv('ECR_REPOSITORY_NAME', STACK_NAME)
LAMBDA_SERVICES_TO_BUILD = os.getenv('LAMBDA_SERVICES_TO_BUILD', 'google_places_collector,json_to_hudi,hudi_to_parquet').split(',')
CLOUDFORMATION_S3_PREFIX = os.getenv('CLOUDFORMATION_S3_PREFIX', 'cloudformation')

# S3 configuration
S3_BUCKET_NAME = STACK_NAME
RAW_DATA_PREFIX = os.getenv('RAW_DATA_PREFIX', 'raw')
HUDI_DATA_PREFIX = os.getenv('HUDI_DATA_PREFIX', 'hudi')
ANALYTICS_DATA_PREFIX = os.getenv('ANALYTICS_DATA_PREFIX', 'analytics')
