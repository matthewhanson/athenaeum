"""
Lambda handler for Athenaeum MCP Server.
Uses AWS Lambda Web Adapter to run FastAPI with uvicorn.

This file is executed during Lambda cold start to prepare the environment.
Lambda Web Adapter will start uvicorn automatically using the AWS_LWA_* environment variables.
"""
import os
from pathlib import Path

def ensure_index():
    """Download index files from S3 to /tmp if needed."""
    import boto3
    
    bucket_name = os.environ.get("ATHENAEUM_INDEX_BUCKET")
    index_dir = Path(os.environ.get("ATHENAEUM_INDEX_DIR", "/tmp/index"))
    
    if not bucket_name:
        return
    
    # Check if index already exists in /tmp
    if index_dir.exists() and any(index_dir.iterdir()):
        return
    
    # Download from S3
    s3 = boto3.client("s3")
    index_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # List and download all files from index/ prefix
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket_name, Prefix="index/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Skip directory markers
                if key.endswith("/"):
                    continue
                
                # Download to /tmp
                local_path = index_dir / key.replace("index/", "")
                local_path.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(bucket_name, key, str(local_path))
    except Exception as e:
        print(f"Warning: Could not download index from S3: {e}")

# Ensure index is available (cold start)
ensure_index()

# Lambda Web Adapter will automatically start uvicorn with:
# uvicorn athenaeum.mcp_server:app --host 0.0.0.0 --port 8080
