# Athenaeum Lambda Deployment Template

This directory contains a **reference template** for deploying Athenaeum as an AWS Lambda function using Docker container images.

## Files in This Template

- **`Dockerfile`** - Example Dockerfile optimized for Lambda with PyTorch CPU
- **`requirements.txt`** - Python dependencies for Lambda runtime
- **`run.sh`** - Lambda Web Adapter startup script
- **`.dockerignore`** - Build optimization (excludes .venv, tests, etc.)
- **`lambda_handler.py`** - *(Legacy)* S3 index download handler (not needed if index is baked in)
- **`oauth_authorizer.py`** - *(Optional)* Lambda authorizer for OAuth/JWT

## Recommended Usage

**For production deployments**, copy this template to your application and customize it:

```bash
# In your application directory (e.g., my-knowledge-base/)
cp -r athenaeum/examples/deployment ./deployment

# Customize your Dockerfile to include your index
cat >> Dockerfile <<'EOF'
# Copy your index into the image (baked in for instant access)
COPY index/ /var/task/index
EOF
```

**Your application structure:**

```
my-application/
├── Dockerfile           # Based on template, customized
├── deployment/
│   ├── requirements.txt
│   └── run.sh
├── index/              # Your vector index (baked into image)
│   ├── docstore.json
│   ├── faiss.index
│   └── ...
└── cdk/
    └── app.py          # CDK deployment
```

## Why Container Images?

AWS Lambda has two deployment options:

1. **Deployment packages** (.zip) - 250MB unzipped limit
2. **Container images** - 10GB uncompressed limit

Athenaeum requires ~2GB for PyTorch + ML dependencies:

- PyTorch (CPU-only): ~900MB
- Transformers + sentence-transformers: ~600MB
- FAISS + LlamaIndex: ~300MB
- FastAPI + dependencies: ~200MB

Container images are the only viable option.

## Deployment Approaches

### Approach 1: Baked-In Index (Recommended)

**Benefits:**

- ✅ Zero cold start latency (no S3 download)
- ✅ Simpler architecture (no S3 bucket)
- ✅ Cost savings (no S3 storage/transfer)
- ✅ Easier versioning (index tied to deployment)

**Your Dockerfile:**

```dockerfile
FROM public.ecr.aws/lambda/python:3.12

COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /var/task

# Install PyTorch CPU-only
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

# Install dependencies
COPY deployment/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install athenaeum (or pip install athenaeum when published)
RUN pip install --no-cache-dir athenaeum

# Bake index into image
COPY index/ /var/task/index

# Startup script
COPY deployment/run.sh /var/task/
RUN chmod +x /var/task/run.sh

ENV PORT=8080
ENV AWS_LWA_INVOKE_MODE=buffered

ENTRYPOINT ["/var/task/run.sh"]
```

**CDK deployment:**

```python
from aws_cdk import Stack, CfnOutput, Duration
from athenaeum.infra import MCPServerContainerConstruct

server = MCPServerContainerConstruct(
    stack, "Server",
    dockerfile_path="./Dockerfile",
    docker_build_context=".",
    index_path=None,  # Index baked into Docker image
    environment={"OPENAI_API_KEY": os.environ["OPENAI_API_KEY"]},
    memory_size=2048,
    timeout=Duration.minutes(5),
)
```

### Approach 2: S3 Download (Legacy, Not Recommended)

Index stored in S3, downloaded to `/tmp` on cold start.

**Downsides:**

- ❌ Adds 5-30s to cold start
- ❌ Requires S3 bucket + IAM permissions
- ❌ More complex architecture

See `lambda_handler.py` for reference implementation.

## Architecture

```
User Request
    ↓
API Gateway (REST API with CORS)
    ↓
Lambda Container (Docker image)
    ├── Lambda Web Adapter (event → HTTP conversion)
    ├── uvicorn (ASGI server)
    ├── FastAPI (athenaeum.mcp_server:app)
    └── Index at /var/task/index
```

**Lambda Web Adapter:**

- AWS's official tool for running web apps on Lambda
- Converts Lambda events ↔ HTTP requests/responses
- Supports buffered and streaming modes
- Zero code changes to FastAPI

**Configuration:**

- `AWS_LWA_INVOKE_MODE=buffered` - Use buffered mode for API Gateway REST API
- `PORT=8080` - Port for uvicorn server

## Dockerfile Explained

The template Dockerfile is optimized for Lambda deployment:

```dockerfile
# Lambda Python 3.12 base (includes AWS Lambda runtime)
FROM public.ecr.aws/lambda/python:3.12

# Install Lambda Web Adapter as Lambda Extension
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /var/task

# Install PyTorch CPU-only first (largest dependency, cache separately)
# CPU-only saves ~800MB vs GPU version
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

# Install application dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install/copy athenaeum
# Production: RUN pip install athenaeum
# Development: COPY src code
COPY src/athenaeum /var/task/athenaeum

# Startup script (must use ENTRYPOINT for shell scripts)
COPY run.sh /var/task/
RUN chmod +x /var/task/run.sh

ENV AWS_LWA_INVOKE_MODE=buffered
ENTRYPOINT ["/var/task/run.sh"]
```

**Layer caching optimization:**

1. PyTorch first (largest, changes rarely)
2. Requirements (changes occasionally)
3. Application code (changes frequently)

## Customization

### Change Memory/Timeout

```python
server = MCPServerContainerConstruct(
    stack, "Server",
    memory_size=4096,  # 4GB for larger models
    timeout=Duration.minutes(10),
)
```

### Change Embedding Model

Edit your index building:

```bash
athenaeum index ./docs \
  --embed-model "sentence-transformers/all-mpnet-base-v2" \
  --output ./index
```

### Add Dependencies

Edit `requirements.txt`:

```txt
# Your additional dependencies
langchain>=0.1.0
```

## Troubleshooting

### Build Fails - Out of Space

Docker build context too large:

```bash
# Verify .dockerignore excludes .venv, cdk.out
cat .dockerignore | grep venv
```

### Lambda 500 Error

Check CloudWatch Logs:

```bash
aws logs tail /aws/lambda/YourStack-ServerFunction-xxx --since 5m
```

Common issues:

- Missing `/var/task/index`
- OPENAI_API_KEY not set
- Memory too low (increase to 2048MB+)

### Container Too Large (>10GB)

```bash
# Check image size
docker images

# Optimize:
# 1. Use PyTorch CPU-only
# 2. Remove unnecessary dependencies
# 3. Multi-stage build to exclude build tools
```

## Cost Estimate

**Lambda:**

- 2GB memory, 2s avg duration
- 10,000 requests/month
- ~$0.50/month

**API Gateway:**

- 10,000 requests/month
- ~$0.035/month

**ECR:**

- 2GB image storage
- ~$0.20/month

**OpenAI API:**

- gpt-4o-mini at $0.15/1M tokens
- Variable based on usage

**Total:** ~$1-2/month for moderate usage

## Further Reading

- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter)
- [AWS CDK Python](https://docs.aws.amazon.com/cdk/api/v2/python/)
