import os
import boto3
import json
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, FloatType, TimestampType, ArrayType, MapType, DoubleType
from datetime import datetime
from pyspark.sql import functions as F
from typing import Optional

def init_spark():
    aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID'] 
    aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY'] 
    session_token = os.environ['AWS_SESSION_TOKEN']

    """Initialize Spark session"""
    return SparkSession.builder \
        .appName("json_to_hudi") \
        .master("local[*]") \
        .config("spark.driver.bindAddress", "127.0.0.1") \
        .config("spark.driver.memory", "1g") \
        .config("spark.executor.memory", "4g") \
        .config("spark.executor.cores", 1) \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.sql.hive.convertMetastoreParquet", "false") \
        .config("spark.hadoop.fs.s3a.access.key", aws_access_key_id) \
        .config("spark.hadoop.fs.s3a.secret.key", aws_secret_access_key) \
        .config("spark.hadoop.fs.s3a.session.token",session_token) \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider","org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider") \
        .getOrCreate()


def process_json_to_hudi(spark: SparkSession, input_path: str, output_path: str):
    """Process JSON data and write to Hudi table"""
    # Read raw JSON
    raw_df = spark.read.option("multiline", True).json(input_path)
    
    # Extract and transform the nested places array
    places_df = raw_df.select("places").withColumn("place", F.explode("places")).select("place.*")
    
    # Handle nested location structure and add timestamp
    df = (
        places_df.select(
            F.col("place_id"),
            F.col("name"),
            F.col("url"),
            F.col("rating"),
            F.col("formatted_address"),
            F.col("types"),
            F.current_timestamp().alias("_timestamp")
        )
        .withColumn("month", F.date_format("_timestamp", "yyyy-MM"))
        .withColumnRenamed("formatted_address", "address")
    )

    # Hudi configs
    hudi_options = {
        'hoodie.table.name': 'beverage_establishments',
        'hoodie.datasource.write.recordkey.field': 'place_id',
        'hoodie.datasource.write.partitionpath.field': 'month',
        'hoodie.datasource.write.table.name': 'beverage_establishments',
        'hoodie.datasource.write.operation': 'upsert',
        'hoodie.datasource.write.precombine.field': 'place_id',
        "hoodie.write.markers.type": "direct",
        "hoodie.embed.timeline.server":"false"
    }
    
    # Write to Hudi
    df.write.format("hudi") \
        .options(**hudi_options) \
        .mode("append") \
        .save(output_path)
    

def extract_s3_path(event):
    """Extract S3 path from event body and convert to s3a format if needed"""
    if isinstance(event, str):
        event = json.loads(event)
    
    # Extract from event body if it exists
    if 'body' in event:
        body = event['body']
        if isinstance(body, str):
            body = json.loads(body)
        if 's3_location' in body:
            return convert_to_s3a(body['s3_location'])
    
    # Try direct s3_location
    if 's3_location' in event:
        return convert_to_s3a(event['s3_location'])
        
    raise ValueError("No s3_location found in event")


def convert_to_s3a(s3_path):
    """Convert s3:// paths to s3a:// for Spark compatibility"""
    if s3_path.startswith('s3://'):
        return s3_path.replace('s3://', 's3a://', 1)
    return s3_path


def lambda_handler(event, context):
    """Lambda handler function"""
    try:
        # Initialize Spark
        spark = init_spark()

        # Extract bucket and key from the S3 event
        source_path = extract_s3_path(event)
        target_bucket = os.environ['TARGET_BUCKET']
        
        # Get location coordinates from environment variables
        location_lat = os.environ.get('LOCATION_LAT', '0.0')
        location_lng = os.environ.get('LOCATION_LNG', '0.0')
        
        # Include lat/lng in the S3 prefix
        target_path = f"s3a://{target_bucket}/{os.environ['HUDI_DATA_PREFIX']}/{location_lat}_{location_lng}/beverage_establishments"

        # Process data
        process_json_to_hudi(spark, source_path, target_path)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully processed JSON to Hudi',
                's3_location': target_path
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise e 