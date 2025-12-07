"""
Bootstrap script for Lambda Web Adapter.

This module is imported at Lambda initialization time to prepare the environment.
Lambda Web Adapter will then start the actual web server.
"""

import os
from pathlib import Path


def download_index():
    """Download index files from S3 to /tmp if needed."""
    import boto3

    bucket_name = os.environ.get("INDEX_BUCKET")
        index_key = os.environ.get("INDEX_KEY", "index/")
        index_dir = Path("/tmp/index")  # noqa: S108    if not bucket_name:
        print("No INDEX_BUCKET configured, skipping index download")
        return

    # Always download on cold start - /tmp may be empty in new execution environment
    print(f"Downloading index from s3://{bucket_name}/{index_key} to {index_dir}")
    s3 = boto3.client("s3")
    index_dir.mkdir(parents=True, exist_ok=True)

    try:
        # List and download all files from index/ prefix
        paginator = s3.get_paginator("list_objects_v2")
        file_count = 0
        for page in paginator.paginate(Bucket=bucket_name, Prefix=index_key):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Skip directory markers
                if key.endswith("/"):
                    continue

                # Download to /tmp
                local_path = index_dir / key.replace(index_key, "")
                local_path.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(bucket_name, key, str(local_path))
                file_count += 1

        # Set INDEX_DIR environment variable
        os.environ["INDEX_DIR"] = str(index_dir)
        print(f"Index downloaded successfully: {file_count} files to {index_dir}")
    except Exception as e:
        print(f"Error downloading index from S3: {e}")
        raise


# Download index during Lambda initialization (cold start)
# This ensures /tmp/index exists before uvicorn starts handling requests
print("Lambda cold start - downloading index...")
download_index()
print("Index ready - uvicorn will start serving requests")
