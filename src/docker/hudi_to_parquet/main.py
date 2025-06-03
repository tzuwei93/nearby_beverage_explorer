import os
import json
import traceback
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


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


def convert_to_s3a(s3_path: str) -> str:
    """Convert s3:// paths to s3a:// for Spark compatibility"""
    if s3_path.startswith('s3://'):
        return s3_path.replace('s3://', 's3a://', 1)
    return s3_path


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


def create_ratings_cols(result_df):
    """Convert wide format to JSON ratings and calculate rating change
    
    Transforms rating columns in wide format (rating_20230101xxxx, rating_20230102xxxx...)
    into a JSON string with format {date1: rating1, date2: rating2} for the history_ratings field
    and calculates the rating change between the most recent and previous rating.
    
    Args:
        result_df: DataFrame with rating_* columns for different timestamps
        
    Returns:
        DataFrame with unique_id, history_ratings, and rating_change
    """
    date_columns = [col for col in result_df.columns if col.startswith("rating_")]
    
    if not date_columns:
        raise ValueError("No rating columns found in the DataFrame")
    
    # Create JSON map with original commit timestamps as keys
    map_pairs = []
    for col in date_columns:
        # Keep the original commit timestamp format from Hudi
        timestamp = col.replace("rating_", "")
        map_pairs.extend([F.lit(timestamp), F.col(col)])
    
    # Create base DataFrame with history_ratings
    base_result = result_df.select(
        F.col("unique_id"),
        F.to_json(
            F.map_filter(
                F.create_map(*map_pairs),
                lambda k, v: v.isNotNull()
            )
        ).alias("history_ratings")
    )
    
    # Calculate rating change if we have at least 2 rating columns
    if len(date_columns) < 2:
        return base_result.withColumn("rating_change", F.lit(0.0))
    
    # Sort by timestamp (strings sort chronologically) - most recent first
    sorted_cols = sorted(date_columns, 
                        key=lambda x: x.replace("rating_", ""), 
                        reverse=True)
    
    most_recent_col = sorted_cols[0]
    previous_col = sorted_cols[1]
    
    # Add rating change calculation
    return base_result.join(
        result_df.select("unique_id", most_recent_col, previous_col),
        on="unique_id",
        how="left"
    ).withColumn(
        "rating_change",
        F.when(
            F.col(most_recent_col).isNotNull() & F.col(previous_col).isNotNull(),
            F.col(most_recent_col) - F.col(previous_col)
        ).otherwise(F.lit(0.0))
    ).select("unique_id", "history_ratings", "rating_change", "name", "latitude", "longitude", "google_maps_url")


def reconstruct_rating_history_from_hudi(spark: SparkSession, basic_info_table_path: str):
    """Reconstruct rating history using Hudi time travel on the basic info table
    
    According to the PRD, Hudi time travel capability is used to construct rating history 
    over time using the beverage basic info table. This function:
    1. Gets all commit timestamps from the basic info table
    2. For each commit, reads the ratings as of that timestamp
    3. Joins all these snapshots into a wide DataFrame
    4. Converts the rating snapshots into JSON format
    5. Calculates rating changes between the most recent and previous ratings
    
    Args:
        spark: SparkSession instance
        basic_info_table_path: Path to the beverage_basic_info_table
        
    Returns:
        DataFrame with unique_id, name, latitude, longitude, history_ratings (JSON), and rating_change,
        or None if reconstruction failed
    """
    try:
        # Get commits from the basic info table (which contains rating data)
        commits = get_hudi_commits(spark, basic_info_table_path)
        if not commits:
            raise ValueError("No commits found in the basic info table")
        
        print(f"Found {len(commits)} commits")
        
        # Get base DataFrame with unique IDs from the latest basic info table
        try:
            basic_info_df = spark.read.format("hudi").load(basic_info_table_path)
            base_df = basic_info_df.select("unique_id", "name", "latitude", "longitude", "google_maps_url")
            # print(f"Using {base_df.count()} unique IDs from basic info table")
        except Exception as e:
            raise ValueError("Failed to read basic info table")
            
        # Join each commit as a column
        result_df = base_df
        for i, commit_ts in enumerate(commits):
            try:
                historical_df = spark.read.format("hudi") \
                    .option("as.of.instant", commit_ts) \
                    .load(basic_info_table_path)
                
                commit_df = historical_df.select(
                    "unique_id",
                    F.col("rating").alias(f"rating_{commit_ts}")
                ).filter(F.col("rating").isNotNull())
                
                result_df = result_df.join(commit_df, on="unique_id", how="left")
                print(f"Processed commit {i+1}/{len(commits)}")
                
            except Exception as e:
                print(f"Error reading commit {commit_ts}: {str(e)}")
                continue
        
        # Convert to JSON format for history_ratings and calculate rating change
        final_df = create_ratings_cols(result_df)
        
        print("Successfully reconstructed rating history from basic info table")
        return final_df
        
    except Exception as e:
        print(f"Error reconstructing rating history: {str(e)}")
        traceback.print_exc()
        return None


def process_hudi_to_parquet(spark: SparkSession, input_path: str, output_path: str):
    """Process Hudi tables to analytics parquet files
    
    This function uses time travel to reconstruct the full history of ratings for each
    beverage shop using the basic info table, and then creates the historical ratings table 
    according to the data model.
    
    Args:
        spark: SparkSession instance
        input_path: Path to Hudi tables
        output_path: Path to write analytics parquet files
    """
    try:
        # Path to basic info table (which contains rating data)
        basic_info_table_path = f"{input_path}/beverage_basic_info_table"
        
        # Reconstruct rating history using time travel on basic info table
        rating_history_df = reconstruct_rating_history_from_hudi(spark, basic_info_table_path)
        
        if rating_history_df is None:
            print("Failed to reconstruct rating history")
            return
        
        # Write to parquet
        rating_history_df.write.mode("overwrite").parquet(output_path)
        print(f"Successfully wrote {rating_history_df.count()} records to analytics parquet at {output_path}")
        
    except Exception as e:
        print(f"Error processing Hudi to parquet: {str(e)}")
        traceback.print_exc()
        raise e


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


def lambda_handler(event, context):
    """Lambda handler function"""
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # Extract paths
        input_path = extract_s3_path(event)
        target_bucket = os.environ['TARGET_BUCKET']
        location_lat = os.environ.get('LOCATION_LAT')
        location_lng = os.environ.get('LOCATION_LNG')
        
        target_path = f"s3a://{target_bucket}/{os.environ['ANALYTICS_DATA_PREFIX']}/{location_lat}_{location_lng}/beverage_analytics"
        
        # Process data
        spark = init_spark()
        
        process_hudi_to_parquet(
            spark, 
            input_path, 
            target_path,
        )
        
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
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f'Error processing Hudi to Parquet: {str(e)}'
            })
        }