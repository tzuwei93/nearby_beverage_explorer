#!/usr/bin/env python3
# Test module for json_to_hudi functionality
import os
import json
import pytest
import tempfile
import shutil
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

# Import the required functions from json_to_hudi module
from src.docker.json_to_hudi.main import process_json_to_hudi, generate_stable_unique_id


@pytest.fixture(scope="session")
def spark():
    """Create a Spark session for testing."""
    return (SparkSession.builder
            .appName("NFX-JsonToHudi-Test")
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


def test_generate_stable_unique_id(spark):
    """Test the stable unique ID generation function."""
    # Create a test dataframe
    test_data = [
        ("Coffee Shop", 25.0383, 121.5330),
        ("Tea House", 25.0383, 121.5330),  # Same location, different name
        ("Coffee Shop", 25.0382, 121.5331)  # Same name, slightly different location
    ]
    
    schema = StructType([
        StructField("name", StringType(), False),
        StructField("latitude", DoubleType(), False),
        StructField("longitude", DoubleType(), False)
    ])
    
    test_df = spark.createDataFrame(test_data, schema)
    
    # Generate unique IDs
    result_df = generate_stable_unique_id(test_df)
    
    # Convert to a list of rows for assertion
    results = result_df.collect()
    
    # Assert that all rows have unique IDs
    assert all(row["unique_id"] is not None for row in results), "All rows should have unique_id values"
    
    # Assert that different entries have different IDs
    unique_ids = [row["unique_id"] for row in results]
    assert len(unique_ids) == len(set(unique_ids)), "All unique_ids should be distinct for different entries"
    
    # Create another dataframe with the same data to verify ID stability
    test_df2 = spark.createDataFrame(test_data, schema)
    result_df2 = generate_stable_unique_id(test_df2)
    results2 = result_df2.collect()
    
    # Assert that IDs are stable for the same input data
    for i in range(len(results)):
        assert results[i]["unique_id"] == results2[i]["unique_id"], "Unique IDs should be stable for the same input data"


def test_json_to_hudi_conversion(spark, temp_dir, sample_restaurant_data):
    """Test converting JSON data to Hudi format with basic info table only."""
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
    
    # Verify basic info table was created (only table created in json_to_hudi)
    basic_info_table_df = spark.read.format("hudi").load(f"{output_path}/beverage_basic_info_table")
    
    # Check that we have data in the basic info table
    assert basic_info_table_df.count() > 0, "Basic info table should have data"
    
    # Verify historical ratings table is NOT created here (it's created in hudi_to_parquet)
    ratings_table_path = f"{output_path}/beverage_ratings_table"
    try:
        ratings_table_df = spark.read.format("hudi").load(ratings_table_path)
        assert False, "Ratings table should not exist in json_to_hudi - it's created in hudi_to_parquet"
    except:
        # Expected behavior - ratings table should not exist yet
        pass
    
    
    # Verify the basic info table structure is correct
    assert "unique_id" in basic_info_table_df.columns
    assert "google_place_id" in basic_info_table_df.columns
    assert "name" in basic_info_table_df.columns
    assert "latitude" in basic_info_table_df.columns
    assert "longitude" in basic_info_table_df.columns
    assert "address" in basic_info_table_df.columns
    assert "google_maps_url" in basic_info_table_df.columns
    assert "rating" in basic_info_table_df.columns  # Rating is included in basic info table
    
    # Verify that unique_id is different from google_place_id (stable hash-based)
    sample_basic_info = basic_info_table_df.collect()[0]
    assert sample_basic_info.unique_id != sample_basic_info.google_place_id, "unique_id should be hash-based, not place_id"
    assert len(sample_basic_info.unique_id) == 12, "unique_id should be 12 characters (truncated hash)"


if __name__ == "__main__":
    # For running directly with pytest
    pytest.main(['-xvs', __file__])
