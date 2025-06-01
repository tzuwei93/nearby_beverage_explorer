#!/usr/bin/env python3
# Test module for hudi_to_parquet functionality
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

# Import the required functions from hudi_to_parquet module
from src.docker.hudi_to_parquet.main import (
    process_hudi_to_parquet,
    reconstruct_rating_history_from_hudi,
    get_hudi_commits
)

# We also need json_to_hudi for test setup
from src.docker.json_to_hudi.main import process_json_to_hudi


@pytest.fixture(scope="session")
def spark():
    """Create a Spark session for testing."""
    return (SparkSession.builder
            .appName("NFX-HudiToParquet-Test")
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
def hudi_test_tables(spark, temp_dir):
    """Create test Hudi tables with sample data."""
    hudi_path = os.path.join(temp_dir, "hudi_tables")
    os.makedirs(hudi_path)
    
    # Helper function to generate stable unique IDs (matching main code logic)
    def generate_test_unique_id(name, lat, lng):
        import hashlib
        normalized_input = f"{name.lower().strip()}_{round(lat, 4)}_{round(lng, 4)}"
        return hashlib.sha256(normalized_input.encode()).hexdigest()[:12]
    
    # Current time for timestamps
    current_time = datetime.now()
    
    # Create Basic Info table with rating data (no last_updated field needed)
    basic_info_data = [
        (generate_test_unique_id("Coffee Shop 1", 25.0412, 121.5652), "place_1", "Coffee Shop 1", "123 Main St", 25.0412, 121.5652, "https://maps.google.com/place1", 4.2),
        (generate_test_unique_id("Cafe 2", 25.0413, 121.5653), "place_2", "Cafe 2", "456 Oak Ave", 25.0413, 121.5653, "https://maps.google.com/place2", 3.8),
        (generate_test_unique_id("Tea House 3", 25.0414, 121.5654), "place_3", "Tea House 3", "789 Pine Rd", 25.0414, 121.5654, "https://maps.google.com/place3", 4.5)
    ]
    basic_info_df = spark.createDataFrame(basic_info_data, ["unique_id", "google_place_id", "name", "address", "latitude", "longitude", "google_maps_url", "rating"])
    basic_info_df.write.format("hudi") \
        .option("hoodie.table.name", "beverage_basic_info_table") \
        .option("hoodie.datasource.write.recordkey.field", "unique_id") \
        .option("hoodie.datasource.write.precombine.field", "rating") \
        .mode("overwrite") \
        .save(f"{hudi_path}/beverage_basic_info_table")
    
    # Create ratings table
    ratings_data = [
        (generate_test_unique_id("Coffee Shop 1", 25.0412, 121.5652), 4.3),
        (generate_test_unique_id("Cafe 2", 25.0413, 121.5653), 3.2),
        (generate_test_unique_id("Tea House 3", 25.0414, 121.5654), 4.5)
    ]
    ratings_df = spark.createDataFrame(ratings_data, ["unique_id", "current_rating"])
    ratings_df.write.format("hudi") \
        .option("hoodie.table.name", "beverage_ratings_table") \
        .option("hoodie.datasource.write.recordkey.field", "unique_id") \
        .option("hoodie.datasource.write.precombine.field", "current_rating") \
        .mode("overwrite") \
        .save(f"{hudi_path}/beverage_ratings_table")
    
    return hudi_path


def test_hudi_analytics_conversion(spark, temp_dir, hudi_test_tables):
    """Test converting Hudi tables to analytics parquet format."""
    # Set up output path for parquet files
    parquet_path = os.path.join(temp_dir, "analytics")
    os.makedirs(parquet_path)
    
    # Current time for testing
    
    # Process Hudi tables to parquet analytics format
    process_hudi_to_parquet(
        spark=spark,
        input_path=hudi_test_tables,
        output_path=parquet_path
    )
    
    # Read and verify the analytics results
    analytics_df = spark.read.parquet(parquet_path)
    
    # Verify structure matches expected schema for historical ratings table
    required_columns = ["unique_id", "name", "latitude", "longitude", "history_ratings", "rating_change"]
    for col in required_columns:
        assert col in analytics_df.columns, f"Missing required column: {col}"
    
    # Verify we have the expected number of records
    assert analytics_df.count() == 3, "Should have 3 establishments in analytics"
    
    # Verify rating changes are correctly calculated (they should be 0.0 for single commit)
    results = {row.unique_id: row for row in analytics_df.collect()}
    
    # With single commit, all rating changes should be 0.0
    for row in analytics_df.collect():
        assert row.rating_change == 0.0, f"{row.name} should have no rating change (single commit)"


def test_rating_history_time_travel(spark, temp_dir):
    """Test the new Hudi time travel approach for rating history reconstruction."""
    # Create sample data with different ratings for time travel testing
    sample_data = [
        {
            "place_id": "ChIJAQAAAQAAAQAAAQAAAQAAAQ",
            "name": "Test Beverage Shop 1",
            "formatted_address": "123 Test Street",
            "geometry": {
                "location": {
                    "lat": 25.0330,
                    "lng": 121.5654
                }
            },
            "url": "https://maps.google.com/?cid=123456789",
            "rating": 4.2,
            "types": ["cafe", "food", "point_of_interest", "establishment"]
        },
        {
            "place_id": "ChIJBQBBBQBBBQBBBQBBBQBBBQ",
            "name": "Test Beverage Shop 2",
            "formatted_address": "456 Test Avenue",
            "geometry": {
                "location": {
                    "lat": 25.0340,
                    "lng": 121.5664
                }
            },
            "url": "https://maps.google.com/?cid=987654321",
            "rating": 3.8,
            "types": ["cafe", "food", "point_of_interest", "establishment"]
        }
    ]
    
    # Create a nested structure with 'places' array as expected by process_json_to_hudi
    sample_json = {"places": sample_data}
    
    # Set up directories
    hudi_output_path = os.path.join(temp_dir, "time_travel_test")
    
    # Write initial data to JSON file
    input_path = os.path.join(temp_dir, "input_data.json")
    with open(input_path, 'w') as f:
        json.dump(sample_json, f)
    
    # Process initial data to create the first commit
    process_json_to_hudi(spark, input_path, hudi_output_path)
    print("✓ Created initial Hudi tables with first commit")
    
    # Wait to ensure timestamps are different
    time.sleep(1)  
    
    # Update ratings and create a second commit
    sample_data[0]["rating"] = 4.5  # First shop rating increased
    sample_data[1]["rating"] = 3.6  # Second shop rating decreased
    
    # Write updated data to a new JSON file
    updated_input_path = os.path.join(temp_dir, "updated_data.json")
    with open(updated_input_path, 'w') as f:
        json.dump({"places": sample_data}, f)
    
    # Process updated data to create second commit
    process_json_to_hudi(spark, updated_input_path, hudi_output_path)
    print("✓ Created second commit with updated ratings")
    
    # Test rating history reconstruction with single-table structure
    basic_info_table_path = os.path.join(hudi_output_path, "beverage_basic_info_table")
    
    # Check commits from basic info table (which now contains rating data)
    commits = get_hudi_commits(spark, basic_info_table_path)
    assert len(commits) >= 2, f"Expected at least 2 commits, got {len(commits)}"
    print(f"✓ Found {len(commits)} commits for time travel testing")
    
    # Reconstruct rating history from basic info table using time travel
    rating_history_df = reconstruct_rating_history_from_hudi(spark, basic_info_table_path)
    assert rating_history_df is not None, "Rating history reconstruction failed"
    
    # Verify rating history structure
    assert "unique_id" in rating_history_df.columns, "Missing unique_id column"
    assert "history_ratings" in rating_history_df.columns, "Missing history_ratings column"
    assert "rating_change" in rating_history_df.columns, "Missing rating_change column"
    
    # Verify each place has the expected rating change
    rating_history_results = rating_history_df.collect()
    assert len(rating_history_results) == 2, f"Expected 2 places in history, got {len(rating_history_results)}"
    
    # Parse JSON ratings to verify
    for row in rating_history_results:
        ratings_dict = json.loads(row.history_ratings)
        assert len(ratings_dict) >= 2, f"Should have at least 2 rating timestamps, got {len(ratings_dict)}"
        
        # Rating changes should match our expected changes
        # One positive change (4.2 -> 4.5 = +0.3) and one negative (3.8 -> 3.6 = -0.2)
        if row.rating_change > 0:
            assert abs(row.rating_change - 0.3) < 0.01, f"Expected rating change of +0.3, got {row.rating_change}"
        else:
            assert abs(row.rating_change + 0.2) < 0.01, f"Expected rating change of -0.2, got {row.rating_change}"
    
    print("✓ Time travel rating history reconstruction test passed!")
    
    # Now let's test the full analytics pipeline with our single-table time travel data
    parquet_path = os.path.join(temp_dir, "time_travel_analytics")
    
    # Process the single-table structure to analytics parquet
    process_hudi_to_parquet(
        spark=spark,
        input_path=hudi_output_path,
        output_path=parquet_path
    )
    
    # Verify the analytics output
    analytics_df = spark.read.parquet(parquet_path)
    
    # Check that we have two records
    assert analytics_df.count() == 2, f"Expected 2 records in analytics output, got {analytics_df.count()}"
    
    # Verify the rating changes are preserved in the analytics output
    has_positive_change = False
    has_negative_change = False
    
    for row in analytics_df.collect():
        if row.rating_change > 0:
            has_positive_change = True
            assert abs(row.rating_change - 0.3) < 0.01, f"Expected rating change of +0.3, got {row.rating_change}"
        elif row.rating_change < 0:
            has_negative_change = True
            assert abs(row.rating_change + 0.2) < 0.01, f"Expected rating change of -0.2, got {row.rating_change}"
    
    assert has_positive_change, "Should have at least one record with positive rating change"
    assert has_negative_change, "Should have at least one record with negative rating change"
    
    print("✓ End-to-end time travel and analytics pipeline test passed!")


def test_get_hudi_commits(spark, hudi_test_tables):
    """Test getting commit timestamps from a Hudi table."""
    basic_info_table_path = f"{hudi_test_tables}/beverage_basic_info_table"
    
    # Get commits
    commits = get_hudi_commits(spark, basic_info_table_path)
    
    # Verify we have at least one commit
    assert len(commits) >= 1, "Should have at least one commit"
    
    # Verify commits are ordered from earliest to latest
    assert sorted(commits) == commits, "Commits should be sorted from earliest to latest"
    
    # Verify commits have the expected format (yyyyMMddHHmmss)
    for commit in commits:
        assert len(commit) >= 14, f"Commit timestamp {commit} should have at least 14 characters"


if __name__ == "__main__":
    # For running directly with pytest
    pytest.main(['-xvs', __file__])
