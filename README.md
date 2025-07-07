# Nearby Beverage Explorer

A comprehensive data pipeline and web application for tracking and analyzing beverage establishments near a specified location. The system collects data from Google Places API, processes it using Apache Hudi for time-travel queries, and presents it through a modern web interface.

![Nearby Beverage Explorer](https://img.shields.io/badge/Status-Active-brightgreen)
![License](https://img.shields.io/badge/License-MIT-blue)

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Data Pipeline](#data-pipeline)
- [S3 Bucket](#s3-bucket)
- [Web Application](#web-application)
- [Testing](#testing)
- [Project Structure](#project-structure)

## Features

- **Automated Data Collection**: Weekly collection of beverage establishment data from Google Places API
- **Time-Travel Analytics**: Track rating changes over time using Apache Hudi
- **Serverless Architecture**: Fully serverless implementation using AWS Lambda and Step Functions
- **Modern Web Interface**: Interactive UI for exploring and filtering beverage establishments
- **Rating Trend Visualization**: Visual representation of rating changes and progression

## Architecture

The project uses a serverless, event-driven architecture:

1. **Data Collection Pipeline**:
   - Google Places API data collection (Lambda)
   - JSON to Apache Hudi conversion (Lambda)
   - Hudi to Parquet conversion for analytics (Lambda)
   - Orchestration via AWS Step Functions

2. **Storage**:
   - S3 for raw data, Hudi tables, and Parquet files
   - ECR for Docker container images

3. **Frontend**:
   - Vue.js web application
   - Hyparquet for client-side Parquet parsing
   - Hosted on S3/CloudFront

## Technology Stack

- **Backend**:
  - Python 3.8
  - Apache Spark 3.3.0
  - Apache Hudi
  - AWS Lambda (containerized)
  - AWS Step Functions
  - AWS EventBridge

- **Frontend**:
  - Vue.js
  - Hyparquet (client-side Parquet parsing)
  - Modern CSS

- **Infrastructure**:
  - AWS CloudFormation (nested stacks)
  - Docker
  - AWS ECR
  - AWS S3

## Getting Started

### Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.8+
- Docker installed and running
- Google Maps API key

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/nearby_beverage_explorer.git
   cd nearby_beverage_explorer
   ```

2. Create a `.env` file based on the example:
   ```bash
   cp .env.example .env
   ```

3. Edit the `.env` file with your configuration:
   ```
   AWS_DEFAULT_REGION=ap-southeast-1
   GOOGLE_MAPS_API_KEY=your_google_maps_api_key
   LOCATION_LAT=25.041171
   LOCATION_LNG=121.565227
   SEARCH_RADIUS_METERS=5000
   S3_BUCKET_NAME=nearby-beverage-explorer
   ```

### Installation

> **Note:** This project uses Poetry for dependency management. The `pyproject.toml` file contains all necessary dependencies (though Docker services still use their own requirements files).

1. Create a Conda environment with Python 3.8:
   ```bash
   conda create -n nearby-beverage python=3.8
   conda activate nearby-beverage
   ```

2. Install Poetry (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Configure Poetry to use the Conda environment:
   ```bash
   poetry config virtualenvs.create false
   ```

4. Install project dependencies with Poetry:
   ```bash
   poetry install
   ```

5. For development dependencies, use:
   ```bash
   poetry install --with dev
   ```

### Deployment

Deploy the entire stack to AWS:

```bash
python deploy/cloudformation_deploy.py
```

This will:
1. Create/update the S3 bucket for data storage
2. Create/update the ECR repository for Docker images
3. Build and push Docker images for Lambda functions
4. Deploy the CloudFormation stack with all resources


## Data Modeling Schema

The system implements a streamlined data model with two core tables:

- **店家基本資訊表 (Beverage Basic Info Table)**
  * unique_id (Primary Key): Stable hash-based identifier (used for internal references)
  * google_place_id: Original Google Places API identifier (used for external references)
  * name: Beverage establishment name
  * address: Full formatted address
  * latitude: Geographic latitude coordinate
  * longitude: Geographic longitude coordinate
  * google_maps_url: Direct link to Google Maps location
  * rating: the rating at the data updated time (0-5 scale)

  > Note: The column `unique_id` is used for this project to prevent the id from Google API changing, and it is constructed using the latitude, longitude, and name of a beverage establishment in order to ensure uniqueness. When the `google_place_id` changes externally, this website will not be influenced, but there might be duplicate entries of the same establishment due to its name being changed slightly or the value of latitude and longitude changing slightly.

- **店家歷史評分表 (Beverage Historical Ratings Table)**
  * unique_id (Primary Key): References the unique_id from the Basic Info table
  * name: the name of the beverage establishment
  * latitude: Geographic latitude coordinate
  * longitude: Geographic longitude coordinate
  * history_ratings: ratings values in JSON format ({date1: rating1, date2: rating2}) from all the commits of the beverage basic info table (Hudi format)
  * rating_change: calculate the rating changes from now to at most past one month

## Data Pipeline

The data pipeline runs weekly (Friday at 6 AM) and consists of three stages:

1. **Google Places Collection**:
   - Fetches beverage establishments data from Google Places API
   - Stores raw JSON data in S3

2. **JSON to Hudi Conversion**:
   - Processes raw JSON data
   - Converts to Apache Hudi format with time-travel capabilities
   - Stores in S3 with appropriate partitioning

3. **Hudi to Parquet Conversion**:
   - Converts Hudi data to Parquet format for efficient querying
   - Optimizes for web application access

### S3 Bucket

The S3 bucket is used to store the raw data, Hudi tables, and Parquet files. The bucket is created by the CloudFormation stack and is named `nearby-beverage-explorer-data`.

#### CORS Configuration for S3 Bucket

When accessing the S3 bucket from a web browser (especially during local development), you might encounter CORS (Cross-Origin Resource Sharing) issues. The following script can be used to configure CORS for your S3 bucket:

```bash
# Configure CORS for a specific bucket and region
./scripts/apply_cors_to_s3.sh --bucket nearby-beverage-explorer-ut-data \
                              --region ap-southeast-1 \
                              --prefix analytics/25.041171_121.565227/beverage_analytics/ \
                              --allow-cors-from-all
```

You can also make the bucket publicly accessible (use with caution):

```bash
# Configure CORS and make the bucket public
./scripts/apply_cors_to_s3.sh --bucket nearby-beverage-explorer-ut-data \
                              --region ap-southeast-1 \
                              --prefix analytics/25.041171_121.565227/beverage_analytics/ \
                              --allow-cors-from-all \
                              --allow-public
```

This script helps resolve CORS issues when developing locally and accessing the S3 bucket directly from your web application. The script will prompt for confirmation before applying changes and display a summary of applied changes when complete.

#### S3 Bucket Structure

```plain
~/dev1/nearby_food_explorer main ?27 ❯ aws s3 ls s3://nearby-beverage-explorer-data/ --recursive                                                                         

2025-05-25 21:43:28          0 analytics/25.041171_121.565227/beverage_establishments/_SUCCESS
2025-05-25 21:43:27       8313 analytics/25.041171_121.565227/beverage_establishments/part-00000-0f7ded4f-71cf-4e07-9ca3-d5eb5ffefbf5-c000.snappy.parquet
2025-05-25 21:35:52          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/.aux/.bootstrap/.fileids/
2025-05-25 21:35:52          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/.aux/.bootstrap/.partitions/
2025-05-25 21:35:51          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/.schema/
2025-05-25 21:43:01          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/.temp/
2025-05-25 21:36:15       1750 hudi/25.041171_121.565227/beverage_establishments/.hoodie/20250525133550354.commit
2025-05-25 21:35:55          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/20250525133550354.commit.requested
2025-05-25 21:36:07        781 hudi/25.041171_121.565227/beverage_establishments/.hoodie/20250525133550354.inflight
2025-05-25 21:43:01       1763 hudi/25.041171_121.565227/beverage_establishments/.hoodie/20250525134242277.commit
2025-05-25 21:42:45          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/20250525134242277.commit.requested
2025-05-25 21:42:52       1478 hudi/25.041171_121.565227/beverage_establishments/.hoodie/20250525134242277.inflight
2025-05-25 21:35:52          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/archived/
2025-05-25 21:36:04        830 hudi/25.041171_121.565227/beverage_establishments/.hoodie/hoodie.properties
2025-05-25 21:35:57          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/.aux/.bootstrap/.fileids/
2025-05-25 21:35:56          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/.aux/.bootstrap/.partitions/
2025-05-25 21:43:00          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/.heartbeat/
2025-05-25 21:35:56          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/.schema/
2025-05-25 21:43:00          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/.temp/
2025-05-25 21:36:03       6641 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/00000000000000.deltacommit
2025-05-25 21:35:59       1452 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/00000000000000.deltacommit.inflight
2025-05-25 21:35:58          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/00000000000000.deltacommit.requested
2025-05-25 21:36:14       6728 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/20250525133550354.deltacommit
2025-05-25 21:36:12       1452 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/20250525133550354.deltacommit.inflight
2025-05-25 21:36:11          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/20250525133550354.deltacommit.requested
2025-05-25 21:42:59       6772 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/20250525134242277.deltacommit
2025-05-25 21:42:57       1452 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/20250525134242277.deltacommit.inflight
2025-05-25 21:42:57          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/20250525134242277.deltacommit.requested
2025-05-25 21:35:56          0 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/archived/
2025-05-25 21:35:57        607 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/.hoodie/hoodie.properties
2025-05-25 21:35:57        124 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/files/.files-0000_00000000000000.log.1_0-0-0
2025-05-25 21:36:02      10928 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/files/.files-0000_00000000000000.log.1_0-7-7
2025-05-25 21:36:13      11016 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/files/.files-0000_00000000000000.log.2_0-39-29
2025-05-25 21:42:58      11016 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/files/.files-0000_00000000000000.log.3_0-26-18
2025-05-25 21:36:01         93 hudi/25.041171_121.565227/beverage_establishments/.hoodie/metadata/files/.hoodie_partition_metadata
2025-05-25 21:36:07         96 hudi/25.041171_121.565227/beverage_establishments/2025-05/.hoodie_partition_metadata
2025-05-25 21:42:54     443015 hudi/25.041171_121.565227/beverage_establishments/2025-05/596faacf-fdaa-4b1f-bf7d-645f6cea0235-0_0-15-11_20250525134242277.parquet
2025-05-25 21:36:09     443015 hudi/25.041171_121.565227/beverage_establishments/2025-05/596faacf-fdaa-4b1f-bf7d-645f6cea0235-0_0-28-22_20250525133550354.parquet
2025-05-25 21:42:26     390139 raw/25.041171_121.565227/places_raw_ce0218de-290f-42da-9c83-1ecdcb685d8e.json
2025-05-25 21:35:36     390139 raw/25.041171_121.565227/places_raw_f854132d-cef2-4252-a022-2036902e87e8.json

```



## Web Application

The web application provides an interactive interface to explore beverage establishments:

- **Search & Filter**: Find establishments by name or rating
- **Rating Changes**: Compare current ratings with previous ones
- **Rating History**: demonstrate ratings
- **Export**: Export data to CSV for further analysis

To run the web application locally:

```bash
cd src/web
npm install
npm run dev
```

## Testing

Run the test suite:

```bash
pytest
```

For specific test files:

```bash
export $(grep -v '^#' .env | xargs) && pytest tests/* -o log_cli=true -vvv tests/test_spark_hudi_functions.py

export $(grep -v '^#' .env | xargs) && pytest -m integration -o log_cli=true -vvv tests/*
```

## Project Structure

```
nearby_beverage_explorer/
├── deploy/                    # Deployment scripts and modules
│   ├── modules/               # Deployment utility modules
│   └── cloudformation_deploy.py # Main deployment script
├── sample_data/               # Sample data for testing
├── scripts/                   # Utility scripts
├── src/
│   ├── cloudformation/        # CloudFormation templates
│   │   ├── serverless.yaml    # Main template
│   │   ├── iam.yaml           # IAM roles and policies
│   │   ├── lambda.yaml        # Lambda functions
│   │   ├── stepfunctions.yaml # Step Functions state machine
│   │   └── storage.yaml       # S3 and ECR resources
│   ├── docker/                # Docker-based Lambda functions
│   │   ├── google_places_collector/ # Google Places API collector
│   │   ├── json_to_hudi/      # JSON to Hudi converter
│   │   └── hudi_to_parquet/   # Hudi to Parquet converter
│   └── web/                   # Web application (Vue.js)
├── tests/                     # Test suite
└── .env.example               # Example environment variables
```
