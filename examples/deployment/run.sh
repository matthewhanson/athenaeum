#!/bin/sh
# Lambda Web Adapter startup script for Athenaeum MCP server

# Download index from S3 if configured
if [ -n "$INDEX_BUCKET" ] && [ -n "$INDEX_KEY" ]; then
    echo "Downloading index from s3://$INDEX_BUCKET/$INDEX_KEY to /tmp/index"
    aws s3 sync "s3://$INDEX_BUCKET/$INDEX_KEY" /tmp/index
    export INDEX_DIR=/tmp/index
fi

# Run the Lambda handler first (downloads index if needed)
python lambda_handler.py

# Start FastAPI server with uvicorn
exec uvicorn athenaeum.mcp_server:app --host 0.0.0.0 --port ${PORT:-8080}
