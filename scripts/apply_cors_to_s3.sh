#!/bin/bash
# S3 CORS apply/test/public script

# ⚠️ CAUTION: This script can make S3 buckets PUBLICLY ACCESSIBLE ⚠️

# Functions
usage() {
  echo "Usage: ./apply_cors_to_s3.sh --bucket <bucket> --region <region> --prefix <prefix> [--allow-cors-from-all] [--allow-public]"
  echo "See script for details."
  exit 1
}

# Parse args & setup
bucket=""; region=""; prefix=""; APPLY_CORS=""; MAKE_PUBLIC=""
CORS_APPLIED=false; PUBLIC_APPLIED=false
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"; exit' EXIT INT TERM

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) bucket="$2"; shift 2 ;;
    --region) region="$2"; shift 2 ;;
    --prefix) prefix="$2"; shift 2 ;;
    --allow-cors-from-all) APPLY_CORS="y"; shift ;;
    --allow-public) MAKE_PUBLIC="y"; shift ;;
    --help|-h) usage ;;
    *) echo "Unknown parameter: $1"; usage ;;
  esac
done

# Check required parameters
if [[ -z "$bucket" || -z "$region" || -z "$prefix" ]]; then
  echo "Error: Required parameters missing."
  usage
fi

# Display warning for public setting
[[ "$MAKE_PUBLIC" == "y" ]] && echo -e "\033[1;33m⚠️  WARNING: Setting bucket '$bucket' to be publicly accessible!\033[0m"

# Create CORS config
cat > "$TMP_DIR/cors.json" << 'EOF'
{"CORSRules":[{"AllowedHeaders":["*"],"AllowedMethods":["GET","HEAD"],"AllowedOrigins":["*"],"ExposeHeaders":[],"MaxAgeSeconds":3000}]}
EOF

# Apply CORS if requested
if [[ -z "$APPLY_CORS" ]]; then
  read -p "Apply CORS to $bucket? (y/n) " APPLY_CORS
fi

if [[ $APPLY_CORS =~ ^[yY]$ ]]; then
  echo "Applying CORS to $bucket ($region)..."
  if aws s3api put-bucket-cors --bucket "$bucket" --cors-configuration "file://$TMP_DIR/cors.json" --region "$region"; then
    CORS_APPLIED=true
    echo "CORS applied successfully."
    
    # Test CORS if requested
    read -p "Test CORS? (y/n) " TEST_CORS
    if [[ $TEST_CORS =~ ^[yY]$ ]]; then
      url="https://${bucket}.s3.${region}.amazonaws.com?list-type=2&prefix=${prefix}&max-keys=100"
      echo "Testing CORS at $url"
      curl -s -I -X OPTIONS "$url" -H "Origin: *" -H "Access-Control-Request-Method: GET" | grep -i "Access-Control"
    fi
  else
    echo "Failed to apply CORS configuration."
  fi
else
  echo "Skipping CORS configuration."
fi

# Apply public policy if requested
if [[ -z "$MAKE_PUBLIC" ]]; then
  read -p "Make bucket $bucket public? (y/n) " MAKE_PUBLIC
fi

if [[ $MAKE_PUBLIC =~ ^[yY]$ ]]; then
  # Extra confirmation for public access
  echo -e "\033[1;31m⚠️  CAUTION: You are making the S3 bucket '$bucket' PUBLICLY ACCESSIBLE\033[0m"
  read -p "Are you ABSOLUTELY SURE? (y/n) " FINAL_CONFIRM
  
  if [[ $FINAL_CONFIRM =~ ^[yY]$ ]]; then
    # Create bucket policy
    cat > "$TMP_DIR/bucket-policy.json" <<EOF
{"Version":"2012-10-17","Statement":[
  {"Sid":"PublicReadGetObject","Effect":"Allow","Principal":"*","Action":"s3:ListBucket","Resource":"arn:aws:s3:::$bucket"},
  {"Sid":"PublicReadGetObject","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::$bucket/*"}
]}
EOF
    if aws s3api put-bucket-policy --bucket "$bucket" --policy "file://$TMP_DIR/bucket-policy.json" --region "$region"; then
      PUBLIC_APPLIED=true
      echo "Public read policy applied successfully."
    else
      echo "Failed to apply public policy."
    fi
  else
    echo "Public access not applied."
  fi
else
  echo "Skipping public access configuration."
fi

# Print summary
echo -e "\n=== Summary ==="
echo "Bucket: $bucket | Region: $region | Prefix: $prefix"
echo "CORS: $(if $CORS_APPLIED; then echo "Applied ✓"; else echo "Not applied ✗"; fi)"
echo "Public: $(if $PUBLIC_APPLIED; then echo "Enabled ✓"; else echo "Not enabled ✗"; fi)"
echo "Done."
