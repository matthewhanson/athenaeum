# AWS Lambda Deployment Guide for Athenaeum

Complete guide for deploying Athenaeum as a serverless AWS Lambda function using Docker container images.

## Table of Contents

- [Overview](#overview)
- [Why Container Images?](#why-container-images)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Deployment Architecture](#deployment-architecture)
- [Step-by-Step Deployment](#step-by-step-deployment)
- [Configuration Reference](#configuration-reference)
- [Testing Your Deployment](#testing-your-deployment)
- [Updating Deployments](#updating-deployments)
- [Troubleshooting](#troubleshooting)
- [Cost Analysis](#cost-analysis)
- [Security Best Practices](#security-best-practices)

## Overview

Athenaeum deploys to AWS Lambda using **Docker container images** to support the full machine learning stack including PyTorch and sentence-transformers. The deployment creates:

- **Lambda Function** - Running FastAPI via Lambda Web Adapter
- **API Gateway** - REST API with CORS support
- **S3 Bucket** - Storage for your vector index
- **CloudWatch Logs** - Monitoring and debugging

## Why Container Images?

Standard AWS Lambda layers have a 250MB unzipped size limit. Athenaeum requires:

- **PyTorch** (CPU-only): ~900MB
- **Transformers**: ~400MB  
- **Sentence-transformers**: ~200MB
- **FAISS + LlamaIndex**: ~200MB
- **FastAPI + dependencies**: ~100MB

**Total: ~1.8GB** - Far exceeding the 250MB layer limit.

Docker container images support up to **10GB**, making them perfect for ML workloads.

## Prerequisites

Before you begin, ensure you have:

1. **AWS Account** with appropriate permissions for:
   - Lambda
   - API Gateway
   - S3
   - IAM
   - ECR (Elastic Container Registry)
   - CloudFormation

2. **AWS CLI** installed and configured:
   ```bash
   aws configure
   # Enter your AWS Access Key ID, Secret Key, and region
   ```

3. **AWS CDK** installed globally:
   ```bash
   npm install -g aws-cdk
   ```

4. **Docker** installed and running:
   ```bash
   docker --version
   # Docker Desktop should be running
   ```

5. **Python 3.12 or higher**:
   ```bash
   python --version
   ```

6. **OpenAI API Key** (or AWS Bedrock access):
   - Get from https://platform.openai.com/api-keys
   - Or configure AWS Bedrock credentials

## Quick Start

### 1. Install Athenaeum

```bash
# Install with deployment extras
pip install athenaeum[deploy,llm-openai]

# Verify installation
athenaeum --version
```

### 2. Build Your Vector Index

```bash
# Index your markdown files
athenaeum index /path/to/your/markdown/files --output ./index

# Example with custom chunking
athenaeum index ./docs \
  --output ./index \
  --chunk-size 2048 \
  --chunk-overlap 400
```

**Chunking recommendations:**
- Documentation/guides: 2048 chunk size, 400 overlap
- Stories/narratives: 3072-4096 chunk size, 800-1200 overlap  
- API references: 1024 chunk size, 200 overlap

### 3. Create Your CDK Project

Create a new directory for your deployment:

```bash
mkdir my-athenaeum-deployment
cd my-athenaeum-deployment
```

Create `app.py`:

```python
#!/usr/bin/env python3
import os
from aws_cdk import App, Stack, CfnOutput, Duration
from athenaeum.infra import MCPServerContainerConstruct

app = App()
stack = Stack(app, "MyAthenaeumStack")

server = MCPServerContainerConstruct(
    stack, "AthenaeumServer",
    # Path to your index directory
    index_path="../index",
    
    # Lambda environment variables
    environment={
        "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
    },
    
    # Lambda configuration
    memory_size=2048,  # 2GB recommended
    timeout=Duration.minutes(5),
)

# Output the API URL
CfnOutput(stack, "ApiUrl", value=server.api_url)
CfnOutput(stack, "FunctionName", value=server.function_name)

app.synth()
```

Create `cdk.json`:

```json
{
  "app": "python3 app.py"
}
```

### 4. Deploy to AWS

```bash
# Set environment variables
export OPENAI_API_KEY=sk-your-openai-key-here
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1

# Bootstrap CDK (first time only in your account/region)
cdk bootstrap

# Deploy
cdk deploy

# Note the ApiUrl output for testing
```

### 5. Test Your Deployment

```bash
# Save the API URL
API_URL="https://abc123.execute-api.us-east-1.amazonaws.com/prod/"

# Health check
curl $API_URL/health

# Search (retrieval only, no LLM)
curl -X POST $API_URL/search \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "limit": 5}'

# Chat (RAG with LLM response)
curl -X POST $API_URL/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is this knowledge base about?"}
    ]
  }'
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Request                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   API Gateway (REST API)                     │
│                     • CORS enabled                           │
│                     • Request/response mapping               │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           AWS Lambda (Container Image - up to 10GB)          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │    Lambda Web Adapter (0.8.4)                         │  │
│  │    • Converts API Gateway events → HTTP              │  │
│  └───────────────────┬───────────────────────────────────┘  │
│                      │                                       │
│  ┌───────────────────▼───────────────────────────────────┐  │
│  │    Uvicorn ASGI Server (port 8080)                    │  │
│  │    • FastAPI application (athenaeum.mcp_server:app)   │  │
│  └───────────────────┬───────────────────────────────────┘  │
│                      │                                       │
│  ┌───────────────────▼───────────────────────────────────┐  │
│  │    Application Stack                                  │  │
│  │    • PyTorch (CPU-only, ~900MB)                       │  │
│  │    • Sentence-transformers (embeddings)               │  │
│  │    • FAISS (vector search)                            │  │
│  │    • LlamaIndex (RAG orchestration)                   │  │
│  └───────────────────┬───────────────────────────────────┘  │
│                      │                                       │
│  ┌───────────────────▼───────────────────────────────────┐  │
│  │    /tmp/index (downloaded from S3 on cold start)      │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      S3 Bucket                               │
│              • Vector index files stored here                │
│              • Downloaded to /tmp on Lambda cold start       │
└─────────────────────────────────────────────────────────────┘
```

### How It Works

1. **Client Request** → API Gateway receives HTTP request
2. **API Gateway** → Invokes Lambda function with event
3. **Lambda Web Adapter** → Converts API Gateway event to HTTP request
4. **Uvicorn** → Handles HTTP request with FastAPI app
5. **FastAPI** → Routes to appropriate endpoint (/search, /chat, etc.)
6. **Athenaeum** → Uses vector index from /tmp to retrieve context
7. **LLM** → Generates response using retrieved context (if /chat)
8. **Response** → Flows back through stack to client

### Cold Start Process

On first invocation (cold start):
1. Lambda initializes container (~5 seconds)
2. Python loads (~2 seconds)
3. `lambda_handler.py` or `run.sh` downloads index from S3 (~5-15 seconds)
4. PyTorch and models load (~3-5 seconds)
5. **Total cold start: 15-27 seconds**

Subsequent requests (warm): **1-2 seconds**

## Step-by-Step Deployment

### Step 1: Prepare Your Index

```bash
# Create index from your markdown files
athenaeum index /path/to/docs --output ./index

# Verify index was created
ls -lh ./index/
# Should see: docstore.json, default__vector_store.json, index_store.json, etc.
```

### Step 2: Understand MCPServerContainerConstruct

The `MCPServerContainerConstruct` is a CDK L3 construct that creates all necessary resources:

```python
from athenaeum.infra import MCPServerContainerConstruct

server = MCPServerContainerConstruct(
    scope,                    # CDK scope (usually 'self' in Stack)
    construct_id,             # Unique ID (e.g., "Server")
    
    # Docker configuration
    dockerfile_path=None,     # Default: athenaeum/examples/deployment/Dockerfile
    docker_build_context=None, # Default: athenaeum root directory
    
    # Index configuration
    index_path="./index",     # Your vector index directory (uploaded to S3)
    
    # Lambda environment
    environment={             # Custom environment variables
        "OPENAI_API_KEY": "sk-...",
    },
    
    # Lambda resources
    memory_size=2048,         # MB (1024-10240)
    ephemeral_storage_size=512, # MB (512-10240) for /tmp
    timeout=Duration.minutes(5), # Max 15 minutes
    
    # Logging
    log_retention=logs.RetentionDays.ONE_WEEK,
    
    # CORS
    cors_allow_origins=["*"], # Allowed origins for CORS
)
```

### Step 3: Create CDK Stack

Create your project structure:

```
my-deployment/
├── app.py          # CDK app entry point
├── cdk.json        # CDK configuration
├── index/          # Your vector index
└── requirements.txt # Python dependencies (optional)
```

**app.py:**

```python
#!/usr/bin/env python3
import os
from aws_cdk import App, Stack, CfnOutput, Duration
from aws_cdk import aws_logs as logs
from athenaeum.infra import MCPServerContainerConstruct

class MyKnowledgeBaseStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        server = MCPServerContainerConstruct(
            self, "Server",
            index_path="./index",
            environment={
                "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
            },
            memory_size=2048,
            timeout=Duration.minutes(5),
            log_retention=logs.RetentionDays.ONE_WEEK,
        )
        
        CfnOutput(self, "ApiUrl", value=server.api_url)
        CfnOutput(self, "FunctionName", value=server.function_name)

app = App()
MyKnowledgeBaseStack(app, "MyKnowledgeBaseStack")
app.synth()
```

**cdk.json:**

```json
{
  "app": "python3 app.py",
  "watch": {
    "include": ["**"],
    "exclude": [
      "README.md",
      "cdk*.json",
      "requirements*.txt",
      "source.bat",
      "**/__init__.py",
      "python/__pycache__",
      "tests"
    ]
  },
  "context": {
    "@aws-cdk/aws-lambda:recognizeLayerVersion": true,
    "@aws-cdk/core:checkSecretUsage": true,
    "@aws-cdk/core:target-partitions": ["aws", "aws-cn"]
  }
}
```

### Step 4: Deploy

```bash
# Set required environment variables
export OPENAI_API_KEY=sk-your-key
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1

# Bootstrap (first time only per account/region)
cdk bootstrap

# View what will be deployed
cdk diff

# Deploy
cdk deploy

# Auto-approve (skip confirmation)
cdk deploy --require-approval never
```

The deployment process:
1. **Synthesizes CloudFormation** template (~10 seconds)
2. **Builds Docker image** with PyTorch (~5-10 minutes first time)
3. **Pushes to ECR** (~2-5 minutes)
4. **Creates CloudFormation stack** (~3-5 minutes)
5. **Uploads index to S3** (~10 seconds - 2 minutes)

**Total first deployment: 15-25 minutes**

Subsequent deployments: 5-10 minutes (Docker layers cached)

## Configuration Reference

### Environment Variables

The Lambda function receives these environment variables:

**Auto-configured by MCPServerContainerConstruct:**
- `PORT`: 8080 (for Lambda Web Adapter)
- `INDEX_BUCKET`: S3 bucket name (if index_path provided)
- `INDEX_KEY`: "index/" (S3 prefix for index files)

**You must provide:**
- `OPENAI_API_KEY`: Your OpenAI API key

**Optional:**
- `ATHENAEUM_INDEX_DIR`: Override index location (default: /tmp/index)
- `AWS_LWA_INVOKE_MODE`: Lambda Web Adapter mode (default: response_stream)

### Memory Sizing Guidelines

| Index Size | Memory | Ephemeral Storage | Cold Start | Warm Time |
|------------|--------|-------------------|------------|-----------|
| < 100MB    | 1024MB | 512MB            | 15-20s     | 1-2s      |
| 100-500MB  | 2048MB | 512MB            | 20-25s     | 1-2s      |
| 500MB-2GB  | 3008MB | 1024MB           | 25-35s     | 2-3s      |
| 2GB+       | 4096MB | 2048MB           | 30-45s     | 2-4s      |

**Formula:** More memory = faster CPU = faster processing

Monitor CloudWatch metrics to optimize:
- `MemoryUsed` - Actual memory consumption
- `Duration` - Function execution time
- `MaxMemoryUsed` - Peak memory

### LLM Provider Configuration

**OpenAI (default):**

```python
environment={
    "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
}
```

Uses `gpt-4o-mini` by default. Configure in your application code via `setup_settings()`.

**AWS Bedrock:**

```python
environment={
    "AWS_ACCESS_KEY_ID": os.environ["AWS_ACCESS_KEY_ID"],
    "AWS_SECRET_ACCESS_KEY": os.environ["AWS_SECRET_ACCESS_KEY"],
}
```

Then configure in code:
```python
from athenaeum.utils import setup_settings
setup_settings(llm_provider="bedrock", llm_model="anthropic.claude-v2")
```

### CORS Configuration

Default allows all origins. For production, restrict:

```python
server = MCPServerContainerConstruct(
    self, "Server",
    cors_allow_origins=[
        "https://yourdomain.com",
        "https://app.yourdomain.com",
    ],
)
```

## Testing Your Deployment

### 1. Get API URL

```bash
# From CDK output
API_URL=$(aws cloudformation describe-stacks \
  --stack-name MyKnowledgeBaseStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)

echo $API_URL
```

### 2. Health Check

```bash
curl $API_URL/health

# Expected response:
# {"status":"healthy","timestamp":"2025-12-03T..."}
```

### 3. Test Search Endpoint

```bash
curl -X POST $API_URL/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Tell me about the main characters",
    "limit": 5
  }'

# Returns: Array of matching text chunks with scores
```

### 4. Test Chat Endpoint

```bash
curl -X POST $API_URL/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is this knowledge base about?"}
    ],
    "model": "gpt-4o-mini",
    "temperature": 0.7
  }'

# Returns: LLM response using RAG context
```

### 5. Monitor CloudWatch Logs

```bash
# Get function name
FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name MyKnowledgeBaseStack \
  --query 'Stacks[0].Outputs[?OutputKey==`FunctionName`].OutputValue' \
  --output text)

# Tail logs in real-time
aws logs tail /aws/lambda/$FUNCTION_NAME --follow

# View last hour
aws logs tail /aws/lambda/$FUNCTION_NAME --since 1h
```

## Updating Deployments

### Update Application Code

If you modify Athenaeum source or dependencies:

```bash
cd my-deployment
cdk deploy
```

This rebuilds the Docker image and updates Lambda.

### Update Index

**Option 1: Redeploy with new index**

```bash
# Rebuild index
athenaeum index /path/to/updated/docs --output ./index

# Redeploy (uploads new index to S3)
cdk deploy
```

**Option 2: Manual S3 sync**

```bash
# Get bucket name
INDEX_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name MyKnowledgeBaseStack \
  --query 'Stacks[0].Outputs[?OutputKey==`IndexBucketName`].OutputValue' \
  --output text)

# Sync updated index
aws s3 sync ./index s3://$INDEX_BUCKET/index/ --delete
```

After updating S3, Lambda will use new index on next cold start.

### Update Environment Variables

Edit `app.py`:

```python
environment={
    "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
    "NEW_VAR": "new_value",
}
```

Then deploy:

```bash
cdk deploy
```

## Troubleshooting

### Docker Build Failures

**Error: "Cannot connect to Docker daemon"**

```bash
# Check Docker is running
docker ps

# On macOS/Windows: Start Docker Desktop
# On Linux: sudo systemctl start docker
```

**Error: "No space left on device"**

```bash
# Clean up Docker
docker system prune -a

# Check available space
df -h
```

**Error: "Dockerfile not found"**

The construct looks for `athenaeum/examples/deployment/Dockerfile` by default. Ensure athenaeum is installed correctly:

```bash
pip show athenaeum
# Should show installation location
```

### Lambda Timeout Errors

**Symptom:** Function times out after 5 minutes

**Solutions:**

1. Increase timeout:
```python
timeout=Duration.minutes(10)  # Max: 15 minutes
```

2. Check cold start time in CloudWatch logs
3. Consider smaller index or chunking
4. Increase memory for faster CPU

### Out of Memory Errors

**Symptom:** `Runtime exited with error: signal: killed`

**Solutions:**

1. Increase memory:
```python
memory_size=3008  # or 4096, 5120, etc.
```

2. Check actual usage in CloudWatch Metrics → Lambda → MemoryUsed

3. Reduce index size or chunk count

### Index Not Loading

**Symptom:** `FileNotFoundError: Index directory not found`

**Check:**

```bash
# Verify S3 bucket exists
aws s3 ls

# Verify index files in bucket
aws s3 ls s3://YOUR-BUCKET/index/

# Check Lambda environment variables
aws lambda get-function-configuration --function-name YOUR-FUNCTION \
  --query 'Environment.Variables'
```

**Verify `lambda_handler.py` or `run.sh` is downloading:**

Check CloudWatch logs for:
```
Downloading index from s3://BUCKET/index/ to /tmp/index
```

### CORS Errors

**Symptom:** Browser shows "CORS policy blocked"

**Fix:** Update allowed origins:

```python
cors_allow_origins=["https://your-frontend-domain.com"]
```

Redeploy:
```bash
cdk deploy
```

### 502 Bad Gateway

**Causes:**
- Lambda function crashed
- Lambda timed out
- Lambda ran out of memory

**Debug:**

1. Check CloudWatch logs for errors
2. Test locally:
```bash
docker build -f examples/deployment/Dockerfile -t test .
docker run -p 8080:8080 -e OPENAI_API_KEY=sk-... test
curl http://localhost:8080/health
```

## Cost Analysis

### Monthly Cost Breakdown (us-east-1)

**Light Usage** (~1,000 requests/month):

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | 1000 requests × 5s × 2GB | $1.50 |
| API Gateway | 1000 requests | $1.00 |
| S3 Storage | 1GB index | $0.50 |
| S3 Requests | 1000 downloads | $0.10 |
| ECR Storage | 2GB image | $0.20 |
| CloudWatch Logs | 100MB | $0.05 |
| **Total** | | **~$3.35** |

**Medium Usage** (~10,000 requests/month):

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | 10,000 requests × 3s × 2GB | $8.00 |
| API Gateway | 10,000 requests | $3.50 |
| S3 | Same as above | $0.60 |
| ECR | Same as above | $0.20 |
| CloudWatch Logs | 500MB | $0.25 |
| **Total** | | **~$12.55** |

**Plus LLM costs:**
- OpenAI gpt-4o-mini: ~$0.15 per 1M input tokens, $0.60 per 1M output tokens
- Average query: ~1000 input tokens, ~500 output tokens
- 1000 queries ≈ $0.45
- 10,000 queries ≈ $4.50

### Cost Optimization Tips

1. **Use smaller models**: gpt-4o-mini instead of gpt-4
2. **Cache responses**: Implement caching for common queries
3. **Optimize chunking**: Smaller chunks = less context = lower LLM costs
4. **Set appropriate timeouts**: Don't pay for hanging requests
5. **Clean old ECR images**: `aws ecr batch-delete-image`
6. **Use S3 Intelligent-Tiering**: For large, infrequently accessed indices
7. **Monitor usage**: Set CloudWatch billing alarms

## Security Best Practices

### 1. Use AWS Secrets Manager for API Keys

```python
from aws_cdk import aws_secretsmanager as secretsmanager

secret = secretsmanager.Secret.from_secret_name(
    self, "OpenAIKey",
    secret_name="athenaeum/openai-api-key"
)

server = MCPServerContainerConstruct(
    self, "Server",
    environment={
        "OPENAI_API_KEY": secret.secret_value.unsafe_unwrap(),
    },
)

secret.grant_read(server.function)
```

### 2. Restrict CORS Origins

```python
cors_allow_origins=["https://yourdomain.com"]
```

### 3. Enable CloudTrail Logging

```bash
aws cloudtrail create-trail \
  --name athenaeum-audit \
  --s3-bucket-name your-audit-bucket

aws cloudtrail start-logging --name athenaeum-audit
```

### 4. Use IAM Authentication

```python
from aws_cdk import aws_apigateway as apigateway

# Require IAM credentials
api = apigateway.RestApi(
    self, "Api",
    default_method_options=apigateway.MethodOptions(
        authorization_type=apigateway.AuthorizationType.IAM,
    ),
)
```

### 5. Enable AWS WAF

Protect against common web attacks:

```python
from aws_cdk import aws_wafv2 as wafv2

web_acl = wafv2.CfnWebACL(
    self, "WebACL",
    scope="REGIONAL",
    default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
    rules=[
        # Add rate limiting, IP blocking, etc.
    ],
    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
        cloud_watch_metrics_enabled=True,
        metric_name="AthenaeumWebACL",
        sampled_requests_enabled=True,
    ),
)
```

### 6. Encrypt Everything

Already configured by default:
- S3 bucket encryption (SSE-S3)
- ECR image encryption
- Lambda environment variables encryption
- CloudWatch Logs encryption

### 7. Set Up CloudWatch Alarms

```python
from aws_cdk import aws_cloudwatch as cloudwatch

# Alert on errors
cloudwatch.Alarm(
    self, "ErrorAlarm",
    metric=server.function.metric_errors(),
    threshold=10,
    evaluation_periods=1,
    alarm_description="Alert when Lambda errors exceed 10",
)

# Alert on high cost
cloudwatch.Alarm(
    self, "CostAlarm",
    metric=server.function.metric_invocations(),
    threshold=100000,
    evaluation_periods=1,
    alarm_description="Alert when invocations exceed 100k per month",
)
```

## Advanced Topics

### Local Testing

Test the Docker container locally before deploying:

```bash
cd /path/to/athenaeum

# Build container
docker build -f examples/deployment/Dockerfile -t athenaeum-test .

# Run container
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=sk-your-key \
  -e INDEX_DIR=/var/task/index \
  -v $(pwd)/index:/var/task/index \
  athenaeum-test

# In another terminal, test
curl http://localhost:8080/health
curl -X POST http://localhost:8080/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 3}'
```

### Custom Dockerfile

Create your own Dockerfile:

```dockerfile
FROM public.ecr.aws/lambda/python:3.12

# Copy Lambda Web Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /var/task

# Install PyTorch CPU-only
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

# Install athenaeum
RUN pip install --no-cache-dir athenaeum[llm-openai]

# Copy startup script
COPY my-startup.sh /var/task/
RUN chmod +x /var/task/my-startup.sh

CMD ["/var/task/my-startup.sh"]
```

Use in CDK:

```python
server = MCPServerContainerConstruct(
    self, "Server",
    dockerfile_path="/path/to/custom/Dockerfile",
    docker_build_context="/path/to/build/context",
)
```

### Multiple Environments

Deploy dev, staging, production:

```python
#!/usr/bin/env python3
import os
from aws_cdk import App, Stack, CfnOutput, Duration, Environment
from athenaeum.infra import MCPServerContainerConstruct

app = App()

env_name = app.node.try_get_context("env") or "dev"

class AthenaeumStack(Stack):
    def __init__(self, scope, id, env_name, **kwargs):
        super().__init__(scope, f"{id}-{env_name}", **kwargs)
        
        server = MCPServerContainerConstruct(
            self, "Server",
            index_path=f"./index-{env_name}",
            environment={
                "ENVIRONMENT": env_name,
                "OPENAI_API_KEY": os.environ[f"OPENAI_API_KEY_{env_name.upper()}"],
            },
            memory_size=2048 if env_name == "prod" else 1024,
        )
        
        CfnOutput(self, "ApiUrl", value=server.api_url)

# Create stacks for each environment
AthenaeumStack(app, "Athenaeum", "dev")
AthenaeumStack(app, "Athenaeum", "staging")
AthenaeumStack(app, "Athenaeum", "prod")

app.synth()
```

Deploy specific environment:

```bash
export OPENAI_API_KEY_DEV=sk-dev-key
cdk deploy Athenaeum-dev

export OPENAI_API_KEY_PROD=sk-prod-key
cdk deploy Athenaeum-prod
```

### Provisioned Concurrency

Keep Lambda warm to eliminate cold starts:

```python
# After creating the construct
version = server.function.current_version
alias = lambda_.Alias(
    self, "LiveAlias",
    alias_name="live",
    version=version,
)

# Configure auto-scaling
scaling = alias.add_auto_scaling(max_capacity=10)
scaling.scale_on_utilization(utilization_target=0.7)

# Note: Provisioned concurrency adds significant cost
# ~$14/month per GB-hour provisioned
```

## Cleanup

Remove all AWS resources:

```bash
# Destroy the stack
cdk destroy

# Confirm when prompted
```

Manual cleanup (if needed):

```bash
# Delete S3 bucket (if retained)
aws s3 rm s3://BUCKET-NAME --recursive
aws s3 rb s3://BUCKET-NAME

# Delete ECR images
aws ecr batch-delete-image \
  --repository-name REPO-NAME \
  --image-ids imageTag=latest

# Delete CloudWatch log groups
aws logs delete-log-group --log-group-name /aws/lambda/FUNCTION-NAME
```

## Support and Resources

- **Athenaeum GitHub**: https://github.com/matthewhanson/athenaeum
- **Issues**: https://github.com/matthewhanson/athenaeum/issues
- **AWS Lambda Container Images**: https://docs.aws.amazon.com/lambda/latest/dg/images-create.html
- **AWS Lambda Web Adapter**: https://github.com/awslabs/aws-lambda-web-adapter
- **AWS CDK Documentation**: https://docs.aws.amazon.com/cdk/
- **LlamaIndex**: https://docs.llamaindex.ai/
- **FastAPI**: https://fastapi.tiangolo.com/

---

**Ready to deploy?** Start with the [Quick Start](#quick-start) section above!
