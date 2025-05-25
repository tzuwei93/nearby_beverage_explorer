#!/usr/bin/env python3
"""
Lambda function to collect nearby places data from Google Places API
"""

import os
import logging
from google_places_client import GooglePlacesClient
from storage import S3Storage

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    AWS Lambda handler function
    
    Args:
        event: Lambda event object
        context: Lambda context object
        
    Returns:
        dict: Lambda response with S3 location of saved data
    """
    try:
        # Get configuration from environment variables
        api_key = os.environ['GOOGLE_MAPS_API_KEY']
        bucket = os.environ['S3_BUCKET_NAME']
        location_lat = float(os.environ['LOCATION_LAT'])
        location_lng = float(os.environ['LOCATION_LNG'])
        # Include lat/lng in the S3 prefix
        raw_prefix = f'{os.environ["RAW_DATA_PREFIX"]}/{location_lat}_{location_lng}'
        radius = int(os.environ['SEARCH_RADIUS_METERS'])
        
        # Initialize clients
        places_client = GooglePlacesClient(api_key)
        storage = S3Storage(bucket, raw_prefix)
        
        # Search for places
        places = places_client.search_nearby_places(
            location_lat=location_lat,
            location_lng=location_lng,
            radius=radius
        )
        
        if not places:
            logger.warning("No places found in the specified area")
            return {
                'statusCode': 200,
                'body': {
                    'message': 'No places found',
                    'location': {
                        'lat': location_lat,
                        'lng': location_lng
                    },
                    'radius': radius
                }
            }
        
        # Enrich with details
        logger.info("Enriching places with details...")
        enriched_places = places_client.enrich_places(places)
        
        # Prepare data for storage
        data = {
            'request_id': context.aws_request_id,
            'location': {
                'lat': location_lat,
                'lng': location_lng
            },
            'radius': radius,
            'places': enriched_places
        }
        
        # Save to S3
        file_name = f"places_raw_{context.aws_request_id}.json"
        s3_location = storage.save_data(data, file_name)
        
        return {
            'statusCode': 200,
            'body': {
                'message': 'Places data collected successfully',
                'count': len(enriched_places),
                's3_location': s3_location,
                'location': {
                    'lat': location_lat,
                    'lng': location_lng
                },
                'radius': radius
            }
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        } 