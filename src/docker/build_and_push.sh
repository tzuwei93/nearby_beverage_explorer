#!/bin/bash

# Exit on any error
set -e

# Default values
REPOSITORY_NAME="nearby-beverage-explorer"
AWS_REGION="ap-southeast-1"
SERVICE_NAME="" # Added: To store the service name from argument

# Function to display usage
usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -r, --repository    Repository name (default: $REPOSITORY_NAME)"
    echo "  -v, --version       Version tag (default: timestamp)"
    echo "      --region        AWS region (default: $AWS_REGION)"
    echo "  -s, --service       Service name (required)" # Added service argument
    echo "  -h, --help         Show this help message"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -r|--repository)
            REPOSITORY_NAME="$2"
            shift 2
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        -s|--service) # Added service argument parsing
            SERVICE_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate that SERVICE_NAME is provided
if [ -z "$SERVICE_NAME" ]; then
    echo "Error: Service name not provided."
    usage
    exit 1
fi

# Ensure AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ]; then
    echo "Failed to get AWS account ID. Please check your AWS credentials."
    exit 1
fi

# ECR repository URL
REPOSITORY_URL="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Login to ECR
echo "Logging in to Amazon ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${REPOSITORY_URL}

# Build and push the specified service
echo "Building ${SERVICE_NAME} service..."

# Service-specific build arguments
case $SERVICE_NAME in
    "google_places_collector")
        build_args="PYSPARK_VERSION=3.3.0;HUDI_FRAMEWORK_VERSION=0.12.2"
        ;;
    "json_to_hudi")
        build_args="PYSPARK_VERSION=3.3.0;HUDI_FRAMEWORK_VERSION=0.12.2"
        ;;
    "hudi_to_parquet")
        build_args="PYSPARK_VERSION=3.3.0;HUDI_FRAMEWORK_VERSION=0.12.2"
        ;;
    *)
        echo "Unknown service: ${SERVICE_NAME}"
        exit 1
        ;;
esac

# Build with service-specific arguments
# Convert semicolon-separated build args into multiple --build-arg flags
build_command="docker build --platform linux/amd64 --provenance=false"
IFS=';' read -ra arg_array <<< "$build_args"
for arg in "${arg_array[@]}"; do
    build_command+=" --build-arg ${arg}"
done

# Add service name argument
build_command+=" --build-arg SERVICE_NAME=${SERVICE_NAME}" # Use SERVICE_NAME variable

# Add tag and context
build_command+=" -t ${REPOSITORY_NAME}:${SERVICE_NAME}-${VERSION}" # Use SERVICE_NAME variable
build_command+=" -f src/docker/Dockerfile ."

# Execute build
echo "Running: $build_command"
eval $build_command

# Tag and push to ECR
echo "Tagging and pushing ${SERVICE_NAME} image..." # Use SERVICE_NAME variable
docker tag ${REPOSITORY_NAME}:${SERVICE_NAME}-${VERSION} ${REPOSITORY_URL}/${REPOSITORY_NAME}:${SERVICE_NAME}-${VERSION} # Use SERVICE_NAME variable
docker push ${REPOSITORY_URL}/${REPOSITORY_NAME}:${SERVICE_NAME}-${VERSION} # Use SERVICE_NAME variable

echo "Service ${SERVICE_NAME} built and pushed successfully!"