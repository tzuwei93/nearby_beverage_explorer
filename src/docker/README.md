# Lambda Functions (Docker-based)

This directory contains the Lambda functions for the Nearby Beverage Explorer project, implemented as Docker containers.

## Structure

```
docker/
├── build_and_push.sh           # Script to build and push images to ECR
├── Dockerfile                  # Common Dockerfile for all services
├── spark-class                # Common spark-class file for Spark-based services
├── google_places_collector/    # Google Places API data collector
│   ├── main.py
│   ├── storage.py
│   ├── google_places_client.py
│   └── requirements.txt
├── json_to_hudi/              # JSON to Apache Hudi converter
│   ├── main.py
│   └── requirements.txt
└── hudi_to_parquet/          # Apache Hudi to Parquet converter
    ├── main.py
    └── requirements.txt
```

## Building and Deploying

The Lambda functions are containerized using AWS Lambda base images. All services share a common Dockerfile and build infrastructure, with service-specific code and dependencies managed separately.

### Prerequisites
1. Docker installed and running
2. AWS credentials configured with ECR access
3. Default AWS Region: `ap-southeast-1` (Singapore)
   - You can override this by specifying a different region in the build script

### Building the Images
Run the build script:
```bash
./build_and_push.sh [aws-region] [repository-name]
```

Examples:
```bash
# Using different repository name
./build_and_push.sh ap-southeast-1 nearby-beverage-explorer
```

## Lambda Modules

Details for each Lambda module within the `src/docker/` directory:

### `google_places_collector`
- **Purpose:** Collects restaurant data from the Google Places API.
- **Environment Variables:**
  - `LOCATION_LAT`
  - `LOCATION_LNG`
  - `SEARCH_RADIUS_METERS`
  - `S3_BUCKET_NAME`
  - `GOOGLE_MAPS_API_KEY`

### `json_to_hudi`
- **Purpose:** Converts JSON data (typically from `google_places_collector`) to Apache Hudi format.
- **Environment Variables:**
  - `TARGET_BUCKET`

### `hudi_to_parquet`
- **Purpose:** Converts data from Apache Hudi format to Parquet format for efficient querying and analytics.
- **Environment Variables:**
  - `TARGET_BUCKET`

## Build Process Details

The build script (`build_and_push.sh`) is responsible for building and pushing a **specific** Lambda service's Docker image to Amazon ECR. It handles the following:

1.  **Argument Parsing:** Accepts arguments for AWS region, ECR repository name, image version, and the **service name** to build (e.g., `google_places_collector`, `json_to_hudi`).
2.  **AWS ECR Login:** Authenticates Docker with your AWS ECR registry.
3.  **Service-Specific Build:**
    *   Identifies the specified service.
    *   Uses the common `Dockerfile` for the build process.
    *   The `Dockerfile` is expected to copy the relevant service-specific Python files (e.g., `main.py`, `requirements.txt`) into the image.
4.  **Image Tagging:** Tags the built image with the ECR repository URL, repository name, service name, and version.
5.  **Image Push:** Pushes the tagged image to the specified AWS ECR repository.

The script requires the service name to be explicitly provided, allowing for individual deployment of each Lambda module.
