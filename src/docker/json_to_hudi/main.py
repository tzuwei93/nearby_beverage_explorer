import os
import boto3
import json
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, FloatType, TimestampType, ArrayType, MapType, DoubleType
from datetime import datetime
from pyspark.sql import functions as F
from typing import Optional


def generate_stable_unique_id(df, name_col="name", lat_col="latitude", lng_col="longitude"):
    """Generate stable unique ID based on normalized name and location
    
    This protects against Google place ID changes externally.
    The ID is stable as long as the business name and location don't change significantly.
    
    Args:
        df: DataFrame with business data
        name_col: Column name containing business name
        lat_col: Column name containing latitude
        lng_col: Column name containing longitude
        
    Returns:
        DataFrame with added 'unique_id' column
    """
    return df.withColumn(
        "unique_id",
        F.sha2(
            F.concat(
                F.lower(F.trim(F.col(name_col))),  # Normalize name (lowercase, trim)
                F.lit("_"),
                F.round(F.col(lat_col), 4).cast("string"),  # ~10m precision
                F.lit("_"),
                F.round(F.col(lng_col), 4).cast("string")
            ), 256
        ).substr(1, 12)  # Use first 12 chars for readability
    )


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


def create_basic_info_table(spark: SparkSession, enriched_df, output_path: str):
    """Create the 店家基本資訊表 (Beverage Basic Info Table)
    Args:
        spark: SparkSession
        enriched_df: DataFrame with enriched Google Places data
        output_path: Path to save the table
        
    Returns:
        DataFrame: The basic info dataframe with generated unique_ids
    """
    beverage_basic_info_df = generate_stable_unique_id(
        enriched_df.select(
            F.col("google_place_id"),
            F.col("name"),
            F.col("address"),
            F.col("latitude"),
            F.col("longitude"),
            F.col("google_maps_url"),
            F.col("rating")
        )
    )
    
    basic_info_table_options = {
        'hoodie.table.name': 'beverage_basic_info_table',
        'hoodie.datasource.write.recordkey.field': 'unique_id',
        'hoodie.datasource.write.partitionpath.field': '',
        'hoodie.datasource.write.table.name': 'beverage_basic_info_table',
        'hoodie.datasource.write.operation': 'upsert',
        "hoodie.write.markers.type": "direct",
        "hoodie.embed.timeline.server": "false",
        "hoodie.datasource.hive_sync.use_jdbc": "false",
    }
    
    beverage_basic_info_df.write.format("hudi") \
        .options(**basic_info_table_options) \
        .mode("append") \
        .save(f"{output_path}/beverage_basic_info_table")
        
    print(f"Created basic info table with {beverage_basic_info_df.count()} records")
    
    return beverage_basic_info_df


def process_json_to_hudi(spark: SparkSession, input_path: str, output_path: str):
    """Process JSON data and write to Hudi tables following PRD data model
    
    This function creates the basic info table with rating data included.
    The historical ratings table will be constructed later in the hudi_to_parquet process
    using Hudi time travel capabilities on the basic info table.
    
    According to the PRD:
    - Basic info table stores current rating along with establishment details
    - Historical ratings table is constructed in hudi_to_parquet using time travel
    """
    # Read raw JSON
    raw_df = spark.read.option("multiline", True).json(input_path)
    
    # Extract and transform the nested places array
    places_df = raw_df.select("places").withColumn("place", F.explode("places")).select("place.*")
    
    # Process places data with location coordinates
    enriched_df = (
        places_df.select(
            F.col("place_id").alias("google_place_id"),  # Google's place_id becomes google_place_id
            F.col("name"),
            F.col("url").alias("google_maps_url"),
            F.col("rating"),
            F.col("formatted_address").alias("address"),
            F.col("types"),
            F.col("geometry.location.lat").alias("latitude"),
            F.col("geometry.location.lng").alias("longitude")
        )
    )

    # Create the basic info table with rating data - this generates the stable unique_ids
    create_basic_info_table(spark, enriched_df, output_path)
    
    print("Successfully created basic info table with stable unique IDs and rating data")
    print("Historical ratings table will be constructed in hudi_to_parquet process using time travel")
    

def extract_s3_path(event):
    """Extract S3 path from event body and convert to s3a format if needed"""

    def convert_to_s3a(s3_path: str) -> str:
        """Convert s3:// paths to s3a:// for Spark compatibility"""
        if s3_path.startswith('s3://'):
            return s3_path.replace('s3://', 's3a://', 1)
        return s3_path

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


def lambda_handler(event, context):
    """Lambda handler function"""
    try:
        # Initialize Spark
        spark = init_spark()

        # Extract bucket and key from the S3 event
        input_path = extract_s3_path(event)
        target_bucket = os.environ['TARGET_BUCKET']
        
        # Get location coordinates from environment variables
        location_lat = os.environ.get('LOCATION_LAT')
        location_lng = os.environ.get('LOCATION_LNG')
        
        # Include lat/lng in the S3 prefix
        target_path = f"s3a://{target_bucket}/{os.environ['HUDI_DATA_PREFIX']}/{location_lat}_{location_lng}/beverage_tables"

        process_json_to_hudi(spark, input_path, target_path)
        
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