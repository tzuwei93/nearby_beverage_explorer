from datetime import datetime, timedelta
import os
import json
from pyspark.sql import SparkSession


def init_spark():
    aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID'] 
    aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY'] 
    session_token = os.environ['AWS_SESSION_TOKEN']

    """Initialize Spark session"""
    return SparkSession.builder \
        .appName("HudiToParquet") \
        .master("local[*]") \
        .config("spark.driver.bindAddress", "127.0.0.1") \
        .config("spark.driver.memory", "1g") \
        .config("spark.executor.memory", "4g") \
        .config("spark.executor.cores", "1") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.sql.hive.convertMetastoreParquet", "false") \
        .config("spark.hadoop.fs.s3a.access.key", aws_access_key_id) \
        .config("spark.hadoop.fs.s3a.secret.key", aws_secret_access_key) \
        .config("spark.hadoop.fs.s3a.session.token",session_token) \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider","org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider") \
        .getOrCreate()


def get_hudi_commits(spark: SparkSession, input_path: str) -> list:
    """Get all commit timestamps from a Hudi table sorted from earliest to latest
    
    Args:
        spark: SparkSession instance
        input_path: Path to the Hudi table
        
    Returns:
        list: List of commit timestamps in the format 'yyyyMMddHHmmss' sorted from earliest to latest,
              or empty list if no commits are found
    """
    jvm = spark._jvm  # Java Virtual Machine interface
    
    hudi_path = convert_to_s3a(input_path)
    
    # Create a meta client to access the Hudi table metadata
    meta_client = jvm.org.apache.hudi.common.table.HoodieTableMetaClient.builder() \
        .setConf(spark._jsc.hadoopConfiguration()) \
        .setBasePath(hudi_path) \
        .build()
    
    timeline = meta_client.getCommitsTimeline().filterCompletedInstants()
    instants = timeline.getInstants().toArray()
    
    if not instants or len(instants) == 0:
        print("No commits found.")
        return []
    
    # Convert to list for sorting
    instants_list = list(instants)
    
    # Sort by timestamp (which is a string in format yyyyMMddHHmmssSSS)
    instants_list.sort(key=lambda x: x.getTimestamp())
    
    # Extract all timestamps
    commit_timestamps = [str(instant.getTimestamp()) for instant in instants_list]
    
    print(f"Found {len(commit_timestamps)} commits: {commit_timestamps}")
    
    return commit_timestamps


def get_earliest_commit_timestamp(spark: SparkSession, input_path: str) -> str:
    """Get the earliest commit timestamp from a Hudi table
    
    Args:
        spark: SparkSession instance
        input_path: Path to the Hudi table
        
    Returns:
        str: The earliest commit timestamp in the format 'yyyyMMddHHmmss'
             or empty string if no commits are found
    """
    commits = get_hudi_commits(spark, input_path)
    
    if not commits:
        return ""
    
    earliest_ts = commits[0]
    print(f"Original Hudi timestamp: {earliest_ts}")
    
    return str(earliest_ts)


def process_hudi_to_parquet(spark: SparkSession, input_path: str, output_path: str, this_week_ts: str, last_week_ts: str) -> None:
    """Process Hudi table to Parquet format with time travel queries for rating comparison
    
    Args:
        spark: SparkSession instance
        input_path: Path to the Hudi table (will be converted to s3a:// if needed)
        output_path: Path where the Parquet output will be written
        this_week_ts: Current week's timestamp
        last_week_ts: Last week's timestamp
    """
    # Get all commits from the Hudi table
    commits = get_hudi_commits(spark, input_path)
    
    if not commits:
        print("No commits found in the Hudi table. Cannot proceed.")
        return

    # Read current week's data
    this_week_df = spark.read.format("hudi") \
        .option("as.of.instant", this_week_ts) \
        .load(input_path)
    
    # Read last week's data
    last_week_df = spark.read.format("hudi") \
        .option("as.of.instant", last_week_ts) \
        .load(input_path)

    # Verify data was loaded, if not using the latest commit
    if this_week_df.count() == 0:
        print(f"Warning: timestamp this week ({this_week_ts}) results in empty data.")
        # Try using the latest commit if different from current timestamp
        if commits[-1] != this_week_ts:
            print(f"Trying latest commit {commits[-1]} instead.")
            this_week_df = spark.read.format("hudi") \
                .option("as.of.instant", commits[-1]) \
                .load(input_path)
    
    # Verify data was loaded, if not using the earliest commit
    if last_week_df.count() == 0:
        print(f"Warning: timestamp last week ({last_week_ts}) results in empty data.")
        # Try using the second latest commit if different from last week timestamp
        if commits[0] != last_week_ts:
            print(f"Trying earliest commit {commits[0]} instead.")
            last_week_df = spark.read.format("hudi") \
                .option("as.of.instant", commits[0]) \
                .load(input_path)
    
    # Register temporary views for SQL queries
    this_week_df.createOrReplaceTempView("this_week_ratings")
    last_week_df.createOrReplaceTempView("last_week_ratings")

    # Show the dataframes
    print(f"Current data (timestamp {this_week_ts}):")
    this_week_df.show()
    print(f"Previous data (timestamp {last_week_ts}):")
    last_week_df.show()

    # Perform comparison analysis using SQL
    comparison_df = spark.sql("""
        SELECT 
            t.place_id,
            t.name,
            t.types,
            t.url,
            t.rating as this_week_rating,
            l.rating as last_week_rating,
            CONCAT(t.rating, ' -> ', l.rating) as rating_progression,
            (t.rating - l.rating) as rating_difference,
            current_timestamp() as updated_at
        FROM this_week_ratings t
        LEFT JOIN last_week_ratings l
        ON t.place_id = l.place_id
    """)
    
    # Write the comparison results to parquet
    comparison_df.write \
        .mode("overwrite") \
        .parquet(output_path)
    
    # Print some statistics
    print("Rating Change Analysis:")
    comparison_df.show()


def extract_s3_path(event):
    """Extract Hudi path from event body and convert to s3a format if needed"""
    if isinstance(event, str):
        event = json.loads(event)
    
    # Extract from event body if it exists
    if 'body' in event:
        body = event['body']
        if isinstance(body, str):
            body = json.loads(body)
        if 's3_location' in body:
            return convert_to_s3a(body['s3_location'])
    
    # Try direct hudi_path
    if 's3_location' in event:
        return convert_to_s3a(event['s3_location'])
        
    raise ValueError("No data_path found in event")


def convert_to_s3a(s3_path: str) -> str:
    """Convert s3:// paths to s3a:// for Spark compatibility
    
    Args:
        s3_path: S3 path that may start with s3:// or s3a://
        
    Returns:
        str: Path with s3a:// protocol for Spark compatibility
    """
    if s3_path.startswith('s3://'):
        return s3_path.replace('s3://', 's3a://', 1)
    return s3_path


def lambda_handler(event, context):
    """Lambda handler function"""
    try:
        print(f"Received event: {json.dumps(event)}")  # Log the event for debugging
        
        # Get parameters from event
        hudi_path = extract_s3_path(event)
        target_bucket = os.environ['TARGET_BUCKET']
        
        # Get location coordinates from environment variables
        location_lat = os.environ.get('LOCATION_LAT', '0.0')
        location_lng = os.environ.get('LOCATION_LNG', '0.0')
        
        # Include lat/lng in the S3 prefix
        target_path = f"s3a://{target_bucket}/{os.environ['ANALYTICS_DATA_PREFIX']}/{location_lat}_{location_lng}/beverage_establishments"
        
        # Initialize Spark
        spark = init_spark()

        # Process data
        process_hudi_to_parquet(
            spark, 
            hudi_path, 
            target_path,
            this_week_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], 
            last_week_ts = (datetime.now() - timedelta(minutes=7*24*60)).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        )
        
        # Stop Spark session
        spark.stop()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Hudi to Parquet processing completed successfully',
                's3_location': target_path,
            })
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f'Error processing Hudi to Parquet: {str(e)}'
            })
        }