import os
import json
import time
import pytest
import tempfile
import shutil
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, ArrayType, TimestampType
from pyspark.sql import functions as F
from datetime import datetime, timedelta

# Import the required functions
# Import using src.docker pattern for local testing
from src.docker.json_to_hudi.main import process_json_to_hudi
from src.docker.hudi_to_parquet.main import process_hudi_to_parquet

@pytest.fixture(scope="session")
def spark():
    """Create a Spark session for testing."""
    return (SparkSession.builder
            .appName("NFX-Test")
            .master("local[*]")  # Run in local mode using all available cores
            .config("spark.jars.packages", "org.apache.hudi:hudi-spark3.3-bundle_2.12:0.12.2")
            .config('spark.serializer', 'org.apache.spark.serializer.KryoSerializer')
            .config('spark.sql.extensions', 'org.apache.spark.sql.hudi.HoodieSparkSessionExtension')
            .config('spark.sql.catalog.spark_catalog', 'org.apache.spark.sql.hudi.catalog.HoodieCatalog')
            .config("spark.sql.warehouse.dir", "file:///tmp/spark-warehouse")
            .config("spark.executor.instances", "1")
            .config("spark.executor.cores", "1")
            .enableHiveSupport()
            .getOrCreate())

@pytest.fixture(scope="function")
def temp_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_restaurant_data():
    """Read sample restaurant data from sample_data/place_details.json for testing."""
    sample_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sample_data', 'place_details.json')
    with open(sample_file_path, 'r') as f:
        data = json.load(f)
    return data

@pytest.fixture
def schema():
    """Define the schema for restaurant data."""
    return StructType([
        StructField("place_id", StringType(), False),
        StructField("name", StringType(), True),
        StructField("rating", DoubleType(), True),
        StructField("formatted_address", StringType(), True),
        StructField("types", ArrayType(StringType()), True),
        StructField("url", StringType(), True),
        StructField("_timestamp", TimestampType(), True)
    ])

def test_json_to_hudi_conversion(spark, temp_dir, sample_restaurant_data):
    """Test converting JSON data to Hudi format."""
    # Create test files
    input_path = os.path.join(temp_dir, "input")
    output_path = os.path.join(temp_dir, "output")
    os.makedirs(input_path)
    os.makedirs(output_path)
    
    # Write sample data
    with open(os.path.join(input_path, "data.json"), "w") as f:
        json.dump(sample_restaurant_data, f)
    
    # Process data
    process_json_to_hudi(
        spark=spark,
        input_path=input_path,
        output_path=output_path
    )
    
    # Verify Hudi dataset was created
    hudi_df = spark.read.format("hudi").load(output_path)
    assert hudi_df.count() == 60

def test_hudi_rating_comparison(spark, temp_dir, schema):
    """Test time travel queries and rating comparison functionality."""
    hudi_path = os.path.join(temp_dir, "hudi")
    parquet_path = os.path.join(temp_dir, "parquet")
    os.makedirs(hudi_path)
    os.makedirs(parquet_path)
    
    # Create test data with different timestamps
    current_time = datetime.now()
    
    # Last week's data
    last_df = (
        spark.createDataFrame([
            ("rest1", "Beverage 1", 4.0, "address1", ["beverage"], "https://www.fakeurl.com", current_time - timedelta(minutes=7)),
            ("rest2", "Cafe 2", 3.5, "address2", ["cafe"], "https://www.fakeurl.com", current_time - timedelta(minutes=7)),
            ("rest3", "Beverage 3", 4.5, "address3", ["beverage"], "https://www.fakeurl.com", current_time - timedelta(minutes=7)),
        ], schema=schema)
        .withColumn("month", F.date_format("_timestamp", "yyyy-MM"))
        .withColumnRenamed("formatted_address", "address")
    )
    
    # Write last week's data
    last_df.write.format("hudi") \
        .option("hoodie.table.name", "beverage_establishments") \
        .option("hoodie.datasource.write.recordkey.field", "place_id") \
        .option("hoodie.datasource.write.precombine.field", "place_id") \
        .option("hoodie.datasource.write.partitionpath.field", "month") \
        .mode("overwrite") \
        .save(hudi_path)
    
    # This week's data (with fake rating changes)
    this_df = (
        spark.createDataFrame([
            ("rest1", "Beverage 1", 4.5, "address1", ["beverage"], "https://www.fakeurl.com", current_time),  # Rating increased
            ("rest2", "Cafe 2", 3.0, "address2", ["cafe"], "https://www.fakeurl.com", current_time),  # Rating decreased
            ("rest3", "Beverage 3", 4.5, "address3", ["beverage"], "https://www.fakeurl.com", current_time)   # Rating unchanged
        ], schema=schema)
        .withColumn("month", F.date_format("_timestamp", "yyyy-MM"))
        .withColumnRenamed("formatted_address", "address")
    )
    
    # sleep to wait for 2 minutes to ensure time travel query works
    time.sleep(120)
    
    # Write this week's data
    this_df.write.format("hudi") \
        .option("hoodie.table.name", "beverage_establishments") \
        .option("hoodie.datasource.write.recordkey.field", "place_id") \
        .option("hoodie.datasource.write.precombine.field", "place_id") \
        .option("hoodie.datasource.write.partitionpath.field", "month") \
        .mode("append") \
        .save(hudi_path)
    
    this_time = current_time.strftime("%Y%m%d%H%M%S")
    last_time = (current_time - timedelta(minutes=2)).strftime("%Y%m%d%H%M%S")

    print(f"This week's timestamp: {this_time}")
    print(f"Last week's timestamp: {last_time}")
    
    process_hudi_to_parquet(
        spark=spark,
        input_path=hudi_path,
        output_path=parquet_path,
        this_week_ts=this_time,
        last_week_ts=last_time
    )
    
    # Read and verify the comparison results
    comparison_df = spark.read.parquet(parquet_path)
    
    # Collect results for verification
    results = comparison_df.collect()
    
    # Verify the number of records
    assert comparison_df.count() == 3, "Should have 3 establishments in comparison"
    
    # Create a dictionary of results for easy lookup
    result_dict = {row.place_id: row for row in results}
    
    # Verify Restaurant 1 (rating increased)
    print (result_dict)
    rest1 = result_dict["rest1"]
    assert rest1.this_week_rating == 4.5
    assert rest1.last_week_rating == 4.0
    assert rest1.rating_progression == "4.5 -> 4.0"
    assert rest1.rating_difference == 0.5
    
    # Verify Restaurant 2 (rating decreased)
    rest2 = result_dict["rest2"]
    assert rest2.this_week_rating == 3.0
    assert rest2.last_week_rating == 3.5
    assert rest2.rating_progression == "3.0 -> 3.5"
    assert rest2.rating_difference == -0.5
    
    # Verify Restaurant 3 (rating unchanged)
    rest3 = result_dict["rest3"]
    assert rest3.this_week_rating == 4.5
    assert rest3.last_week_rating == 4.5
    assert rest3.rating_progression == "4.5 -> 4.5"
    assert rest3.rating_difference == 0.0 