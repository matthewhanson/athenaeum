# Simple Athenaeum Deployment Example

This example demonstrates the **recommended high-level approach** for deploying Athenaeum to AWS Lambda using container images.

## What's Included

- **`app.py`** - CDK app entry point
- **`stacks/simple_stack.py`** - Example using `MCPServerContainerConstruct` (high-level)
- **`stacks/athenaeum_stack_lowlevel_reference.py.bak`** - Low-level reference (not recommended)

## Why Container-Based Deployment?

The `MCPServerContainerConstruct` uses Docker container images which:

- ✅ Support up to **10GB** (vs 250MB layer limit)
- ✅ Include full **PyTorch** stack (~900MB)
- ✅ Include **sentence-transformers** for embeddings
- ✅ Simple single-construct deployment
- ✅ Automatic S3 index upload/download

## Quick Start

### Prerequisites

```bash
# Install AWS CDK
npm install -g aws-cdk

# Ensure Docker is running
docker --version

# Set environment variables
export OPENAI_API_KEY=sk-your-key-here
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1
```

### Build Your Index

```bash
# From athenaeum root
athenaeum index /path/to/your/docs --output ./examples/simple-deployment/index
```

### Deploy

```bash
# From this directory
cd examples/simple-deployment

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy
cdk deploy
```

## Stack Overview

The `SimpleAtheneumStack` creates:

- **Lambda Function** - Container-based, 2GB memory, 5min timeout
- **API Gateway** - REST API with CORS
- **S3 Bucket** - Stores your vector index
- **CloudWatch Logs** - 7-day retention
- **ECR Image** - ~2GB Docker image with PyTorch

## Configuration

Edit `stacks/simple_stack.py` to customize:

```python
server = MCPServerContainerConstruct(
    self,
    "Server",
    index_path=str(index_path) if index_path.exists() else None,

    environment={
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
    },

    # Adjust resources as needed
    memory_size=2048,  # 1024-10240 MB
    ephemeral_storage_size=512,  # /tmp storage
    timeout=Duration.minutes(5),  # 1s-15min

    log_retention=logs.RetentionDays.ONE_WEEK,
    cors_allow_origins=["*"],  # Restrict in production!
)
```

## Using AWS Bedrock Instead of OpenAI

To use AWS Bedrock for the LLM:

1. Remove `OPENAI_API_KEY` from environment
2. Grant Lambda IAM permissions for Bedrock
3. The application will auto-detect and use Bedrock

## Cost Estimate

For light usage (~1000 requests/month):

- **Lambda**: $3-4/month (includes compute + ECR storage)
- **API Gateway**: $0.50/month
- **S3**: $0.10/month
- **CloudWatch Logs**: $0.50/month

### Total Cost

Approximately $4-5/month

## Next Steps

1. **Test your deployment**:

   ```bash
   curl -X POST https://your-api-url/chat \
     -H "Content-Type: application/json" \
     -d '{"question": "What is Athenaeum?"}'
   ```

2. **Review the DEPLOYMENT.md** in the athenaeum root for detailed configuration options

3. **Customize for production**:
   - Use AWS Secrets Manager for API keys
   - Restrict CORS origins
   - Add authentication
   - Configure custom domain

## Troubleshooting

### "Docker daemon not running"

```bash
# Start Docker Desktop
```

### "No index found"

```bash
# Build an index first
athenaeum index /path/to/docs --output ./index
```

### "OPENAI_API_KEY not set"

```bash
export OPENAI_API_KEY=sk-your-key
```

## Reference

- **Main Documentation**: See `../../DEPLOYMENT.md`
- **Container Construct**: `src/athenaeum/infra/mcp_server_container.py`
- **Docker Image**: `examples/deployment/Dockerfile`
