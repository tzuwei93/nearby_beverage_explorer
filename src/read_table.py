"""
Script to read data from Louisa popularity JSON files
"""
import os
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
import pyarrow as pa

def init_spark():
    """Initialize Spark session"""
    return SparkSession.builder \
        .appName("Louisa Popularity Reader") \
        .getOrCreate()

def read_with_spark(table_path):
    """Read JSON files using PySpark"""
    spark = init_spark()
    
    # Read JSON data
    df = spark.read.json(table_path)
    print("\n=== Latest Data ===")
    df.show()
    
    # Get average popularity by date
    print("\n=== Average Popularity by Date ===")
    df.groupBy("date").agg({"current_popularity": "avg"}).show()
    
    # Get today's data
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n=== Today's Data ({today}) ===")
    df.filter(f"date = '{today}'").show()
    
    return spark

def convert_spark_to_arrow(spark_df):
    """Convert Spark DataFrame to Arrow Table"""
    return pa.Table.from_pandas(spark_df.toPandas())

def main():
    """Main function"""
    # Path to the JSON files
    table_path = os.path.join("data", "louisa_popularity", "data")
    
    print("Reading with PySpark...")
    try:
        spark = read_with_spark(table_path)
        
        # Convert to Arrow format if needed
        df = spark.read.json(table_path)
        arrow_table = convert_spark_to_arrow(df)
        print("\n=== Data in Arrow format ===")
        print(arrow_table.schema)
        print(arrow_table.to_pandas())
        
        # Clean up Spark session
        spark.stop()
    except Exception as e:
        print(f"Error reading data: {str(e)}")
        import traceback
        print(f"Stack trace:\n{traceback.format_exc()}")

if __name__ == "__main__":
    main() 