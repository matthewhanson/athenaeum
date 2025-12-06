#!/bin/sh
# Lambda Web Adapter startup script for Athenaeum MCP server

# Index is baked into the Docker image at /var/task/index
# No S3 download needed - instant startup!

# Start FastAPI server with uvicorn
# Lambda Web Adapter will proxy requests to this server
echo "Starting uvicorn server with index at /var/task/index..."
exec uvicorn athenaeum.mcp_server:app --host 0.0.0.0 --port ${PORT:-8080}
