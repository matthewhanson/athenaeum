"""
Bootstrap script for Lambda Web Adapter.

This module is imported at Lambda initialization time to prepare the environment.
Lambda Web Adapter will then start the actual web server.

Note: With container-based deployment, the index is typically baked into the
Docker image at /var/task/index. This bootstrap file is kept minimal.
"""

import os
from pathlib import Path


def setup_environment():
    """Set up environment variables for the Lambda function."""
    # Index should be baked into container at /var/task/index
    # But allow override via environment variable
    index_dir = os.environ.get("INDEX_DIR", "/var/task/index")

    # Verify index exists
    if not Path(index_dir).exists():
        print(f"Warning: Index directory not found at {index_dir}")
        print("Expected index to be baked into container image")
    else:
        print(f"Index ready at {index_dir}")

    os.environ["INDEX_DIR"] = index_dir


# Run setup during Lambda initialization (cold start)
print("Lambda cold start - setting up environment...")
setup_environment()
print("Environment ready - uvicorn will start serving requests")
