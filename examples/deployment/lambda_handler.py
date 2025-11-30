"""
Lambda handler for Athenaeum MCP Server.
Uses Mangum to adapt FastAPI to AWS Lambda.
"""
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mangum import Mangum
from athenaeum.mcp_server import app

# Download index from S3 if not in Lambda package
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

# Create Mangum handler
handler = Mangum(app, lifespan="off")
