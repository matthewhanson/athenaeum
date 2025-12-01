# AWS Lambda Deployment Guide

This guide covers deploying Athenaeum as a serverless Lambda function using AWS CDK.

## Quick Summary

**Athenaeum** is a library for building RAG (Retrieval-Augmented Generation) systems over markdown documentation. This deployment guide shows two approaches:

1. **Using Athenaeum's Infrastructure Constructs** (Recommended)
2. **Custom Deployment** (Advanced)

The constructs provide:
- **DependenciesLayerConstruct** - Lambda layer with PyTorch CPU, LlamaIndex, FAISS (~1.2GB optimized)
- **MCPServerConstruct** - Complete FastAPI server with Lambda Web Adapter, API Gateway, S3

## Architecture

```
Client
  ↓
API Gateway (HTTP → Lambda)
  ├─ CORS support
  └─ Routes: /search, /chat/completions, /health
  ↓
Lambda Function
  ├─ Lambda Web Adapter (port 8080)
  ├─ FastAPI (athenaeum.mcp_server:app)
  ├─ Dependencies Layer (PyTorch CPU, LlamaIndex, FAISS)
  └─ Function Code (deployment scripts)
  ↓
S3 Bucket
  └─ Index files (FAISS, docstore, metadata)
```

## Prerequisites

1. **AWS Account** with appropriate permissions (Lambda, API Gateway, S3, IAM)
2. **AWS CLI** configured: `aws configure`
3. **AWS CDK**: `npm install -g aws-cdk`
4. **Python 3.12+**
5. **UV** package manager (recommended) or pip
6. **OpenAI API key** (or Ollama for local development)

## Deployment Approach 1: Using Infrastructure Constructs (Recommended)

The simplest way to deploy is using Athenaeum's reusable CDK constructs.

### Quick Start

```python
# app.py
from aws_cdk import App, Stack
from athenaeum.infra import DependenciesLayerConstruct, MCPServerConstruct

app = App()
stack = Stack(app, "MyKnowledgeBase")

# Create dependencies layer (handles PyTorch, LlamaIndex, FAISS)
deps = DependenciesLayerConstruct(stack, "Deps")

# Create MCP server (Lambda + API Gateway + S3)
server = MCPServerConstruct(
    stack, "Server",
    dependencies_layer=deps.layer,
    index_path="./index",  # Your vector index
    environment={
        "OPENAI_API_KEY": "sk-...",  # Better: use Secrets Manager
    },
)

app.synth()
```

Deploy:
```bash
cdk deploy
```

### Benefits

- **~20 lines** instead of ~200
- **Best practices built-in**: CPU-only PyTorch, size optimization, proper IAM
- **Versioned API**: Constructs are semver'd with athenaeum package
- **No boilerplate**: All infrastructure logic encapsulated
- **Fast rebuilds**: Cached dependencies layer

### Example

See `examples/simple-deployment/` for a complete working example.

## Deployment Approach 2: Custom CDK Stack

For full control over infrastructure, you can write your own CDK stack. This approach gives you more flexibility but requires more code.

### Installation

```bash
# Clone or navigate to athenaeum
cd athenaeum

# Install with deployment extras
uv sync --extra deploy

# Or with pip
pip install -e ".[deploy]"
```

### Configure AWS CDK

```bash
# Set environment
export AWS_REGION=us-east-1
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=$AWS_REGION

# Bootstrap CDK (first time only)
cdk bootstrap
```

### Custom Stack Example

See `examples/simple-deployment/stacks/athenaeum_stack.py` for a full custom CDK stack implementation showing:
- PyTorch CPU-only installation (avoids 7GB+ CUDA libraries)
- Lambda layer size optimization (~1.2GB → ~300MB compressed)
- Lambda Web Adapter integration
- S3 bucket for index storage
- API Gateway with CORS

## Building Your Index

Before deploying, create your index locally:

```bash
# Simple indexing
athenaeum index ./docs --output ./index

# Advanced: Custom chunk sizes for different content types
# For RPG rules/mechanics (balanced)
athenaeum index ./rules \
  --output ./index \
  --chunk-size 2048 \
  --chunk-overlap 400

# For timelines/narratives (larger chunks preserve context)
athenaeum index ./timelines \
  --output ./index \
  --chunk-size 3072 \
  --chunk-overlap 800

# Exclude patterns
athenaeum index ./docs \
  --output ./index \
  --exclude "**/.git/**" "**/__pycache__/**" "**/*.png"
```

**Chunking Strategy:**
- **Small docs (APIs, references)**: 1024 chunks, 200 overlap
- **Medium docs (guides, rules)**: 2048-3072 chunks, 400-600 overlap
- **Large docs (narratives)**: 3072-4096 chunks, 800-1200 overlap
- **Overlap**: 20-30% of chunk size for continuity

The `MarkdownNodeParser` automatically preserves heading hierarchy regardless of chunk size.

## CDK Stack Architecture

### Two-Layer Bundling Strategy

**Problem:** Bundling everything together made deploys slow (5+ minutes every time)

**Solution:** Separate cached dependencies from fast-changing code

**Dependencies Layer** (slow, cached):
- Bundles athenaeum package + all PyPI dependencies
- Only rebuilds when `requirements.txt` or athenaeum source changes
- Uses Docker bundling in CDK for consistent Linux builds
- Size: ~200-400 MB (includes PyTorch, FAISS, LlamaIndex)

**Function Layer** (fast, rebuilds every time):
- Just deployment scripts (`lambda_handler.py`, `oauth_authorizer.py`)
- Creates `run.sh` script for Lambda Web Adapter
- Rebuilds in seconds
- Size: < 1 MB

### Example CDK Stack

See `examples/cdk/stacks/athenaeum_stack.py` for the complete example. Key points:

```python
# Dependencies layer - cached
dependencies_layer = lambda_.LayerVersion(
    code=lambda_.Code.from_asset(
        str(project_root.parent),  # Access parent to get athenaeum package
        bundling={
            "command": [
                "pip install -r requirements.txt -t /asset-output/python",
                "pip install /asset-input/athenaeum -t /asset-output/python",
            ]
        }
    )
)

# Function layer - fast rebuilds
mcp_lambda = lambda_.Function(
    code=lambda_.Code.from_asset(
        str(project_root / "deployment"),
        bundling={
            "command": [
                "cp lambda_handler.py /asset-output/",
                "echo 'exec uvicorn athenaeum.mcp_server:app ...' > /asset-output/run.sh",
            ]
        }
    ),
    layers=[dependencies_layer, web_adapter_layer]
)
```

## Usage

### Get Your API Endpoint

```bash
aws cloudformation describe-stacks \
  --stack-name AtheneumStack \
  --query 'Stacks[0].Outputs[?OutputKey==`APIEndpoint`].OutputValue' \
  --output text
```

### Test Endpoints

**Without OAuth (public access):**

```bash
# Health check
curl https://YOUR_API_ENDPOINT/health

# Search (retrieval only, no LLM)
curl -X POST https://YOUR_API_ENDPOINT/search \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "limit": 5}'

# Chat (RAG with LLM response)
curl -X POST https://YOUR_API_ENDPOINT/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "What is this documentation about?"}]
  }'
```

**With OAuth (requires token):**

```bash
# Get access token from your OAuth provider first
TOKEN="eyJhbGc..."

# Then add Authorization header
curl -X POST https://YOUR_API_ENDPOINT/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "your query", "limit": 5}'
```

## Updating Your Deployment

### Fast Iteration with --hotswap

When making frequent changes to Lambda **function code only** (not dependencies, infrastructure, or IAM), use `--hotswap` for much faster deployments:

```bash
# Standard deployment: 2-3 minutes (full CloudFormation update)
cdk deploy

# Hotswap deployment: 10-30 seconds (bypasses CloudFormation)
cdk deploy --hotswap
```

**What --hotswap does:**

1. **Detects code-only changes**: Compares your local changes against deployed stack
2. **Bypasses CloudFormation**: Directly updates Lambda via AWS SDK (`UpdateFunctionCode` API)
3. **Skips changeset creation**: No waiting for CloudFormation to plan/execute
4. **Updates immediately**: New code is live in seconds instead of minutes

**What --hotswap does NOT do:**

- ❌ Update dependencies layer (requires full `cdk deploy`)
- ❌ Change infrastructure (API Gateway, S3, IAM, etc.)
- ❌ Modify environment variables
- ❌ Update resource configurations (memory, timeout, etc.)

**When to use --hotswap:**

- ✅ Fixing bugs in `lambda_handler.py` or `athenaeum/` source code
- ✅ Tweaking FastAPI routes or response formatting
- ✅ Adjusting LLM prompts or retrieval logic
- ✅ Rapid development/testing cycles

**When to use full `cdk deploy`:**

- 🔄 Updated `requirements.txt` (new packages or versions)
- 🔄 Changed Lambda memory, timeout, or other settings
- 🔄 Modified environment variables
- 🔄 Infrastructure changes (new API routes, S3 buckets, etc.)

**Safety Notes:**

- `--hotswap` is **development-only** - never use in production CI/CD pipelines
- Falls back to full deployment if infrastructure changes detected
- CloudFormation drift: Your stack's actual state diverges from template until next full deploy
- Always do a final `cdk deploy` (without --hotswap) before production

**Typical Workflow:**

```bash
# 1. Initial deployment (full)
cdk deploy

# 2. Fix bug in lambda_handler.py
# Edit code...
cdk deploy --hotswap  # 15 seconds

# 3. Test, find another issue
# Edit code...
cdk deploy --hotswap  # 15 seconds

# 4. Update requirements.txt (need new package)
# Edit requirements.txt...
cdk deploy  # 2-3 minutes (full - rebuilds dependencies layer)

# 5. More code tweaks
# Edit code...
cdk deploy --hotswap  # 15 seconds

# 6. Ready to merge? Final full deployment
cdk deploy  # Ensures CloudFormation state is correct
```

### Update Scenarios

**Scenario 1: Code-only changes (use --hotswap)**
```bash
# Made changes to athenaeum source code or lambda_handler.py
cdk deploy --hotswap
```

**Scenario 2: Dependency changes (full deploy required)**
```bash
# Updated requirements.txt or athenaeum package version
# Dependencies layer will rebuild (~2-3 min first time, then cached)
cdk deploy
```

**Scenario 3: Infrastructure changes (full deploy required)**
```bash
# Changed Lambda memory, added environment variables, modified IAM, etc.
cdk deploy
```

### Update Index

```bash
# Rebuild index locally
athenaeum index ./docs --output ./index

# Deploy (CDK auto-uploads to S3 if index/ exists)
cd examples
cdk deploy --hotswap

# Or manually sync to S3
INDEX_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name AtheneumStack \
  --query 'Stacks[0].Outputs[?OutputKey==`IndexBucketName`].OutputValue' \
  --output text)
aws s3 sync ./index s3://$INDEX_BUCKET/index/ --delete
```

## Local Development

### CLI Usage

The athenaeum CLI is now optimized with lazy imports:

```bash
# Instant help (< 0.1s with lazy imports)
athenaeum --help

# Build index
athenaeum index ./docs --output ./index

# Search without LLM
athenaeum search "your query" --output ./index --top-k 5

# Chat with LLM (uses OpenAI by default)
athenaeum chat "your question" --output ./index

# Use Ollama instead
athenaeum chat "your question" \
  --llm-provider ollama \
  --llm-model llama3.1:8b
```

### MCP Server Locally

```bash
# Set environment
export OPENAI_API_KEY=sk-...
export ATHENAEUM_INDEX_DIR=./index

# Run server
athenaeum serve --index ./index --port 8000

# Or use uvicorn directly
uvicorn athenaeum.mcp_server:app --reload --port 8000
```

## Lambda Configuration

### Environment Variables

Set in Lambda console or via CDK:

```python
environment={
    # Required
    "ATHENAEUM_INDEX_BUCKET": "your-bucket-name",
    "ATHENAEUM_INDEX_DIR": "/tmp/index",
    
    # OpenAI (recommended for production)
    "OPENAI_API_KEY": "sk-...",  # Use Secrets Manager in production
    
    # OAuth (if enabled)
    "OAUTH_ISSUER": "https://...",
    "OAUTH_AUDIENCE": "...",
    
    # Lambda Web Adapter
    "AWS_LWA_INVOKE_MODE": "response_stream",
    "AWS_LWA_PORT": "8080",
}
```

### Resource Limits

Adjust based on your index size and query complexity:

```python
# Small indices (<500MB)
memory_size=1024  # MB
timeout=30  # seconds

# Medium indices (500MB-2GB)
memory_size=2048
timeout=60

# Large indices (2GB+) or complex queries
memory_size=3008  # Up to 10,240
timeout=120  # Up to 900 (15 minutes)
```

## Troubleshooting

### Common Issues

**1. Lambda Timeout**
- Increase timeout in CDK stack
- Check index download time (large indices from S3)
- Monitor CloudWatch logs for bottlenecks

**2. Out of Memory**
- Increase Lambda memory allocation
- Use smaller embedding models
- Reduce chunk size or number of chunks loaded

**3. OAuth "Unauthorized"**
- Verify token hasn't expired
- Check issuer/audience match exactly
- Ensure JWKS URL is accessible from Lambda
- Review authorizer CloudWatch logs

**4. Index Not Loading**
- Verify S3 bucket permissions (CDK creates these automatically)
- Check index files uploaded: `aws s3 ls s3://BUCKET/index/`
- Review Lambda logs: `aws logs tail /aws/lambda/FUNCTION_NAME --follow`

**5. Slow Cold Starts**
- Index download from S3 takes time (proportional to size)
- Consider provisioned concurrency for critical workloads
- Use smaller indices or Lambda SnapStart when available for Python

### Debugging

**View Lambda Logs:**
```bash
aws logs tail /aws/lambda/AtheneumStack-MCPServerFunction --follow
```

**Check Stack Status:**
```bash
cdk diff  # See what would change
cdk ls    # List all stacks
```

**Test Locally First:**
```bash
# Always test locally before deploying
export ATHENAEUM_INDEX_DIR=./index
export OPENAI_API_KEY=sk-...
uvicorn athenaeum.mcp_server:app --reload
```

## Cost Optimization

**Monthly cost estimates** (us-east-1, light usage ~1000 requests/month):
- Lambda: ~$1-2
- API Gateway: ~$1
- S3: ~$0.50 (1GB index)
- **Total: ~$2-4/month**

**Medium usage** (~10,000 requests/month):
- Lambda: ~$5-10
- API Gateway: ~$3-5
- S3: ~$0.50
- **Total: ~$8-16/month**

**Optimization tips:**
- Use smaller embedding models (all-MiniLM-L6-v2 vs larger models)
- Enable response caching in API Gateway
- Use provisioned concurrency sparingly (adds ~$14/month per GB-hour)
- Clean up old Lambda versions
- Enable S3 Intelligent-Tiering for infrequent access

## Security Best Practices

1. **Use AWS Secrets Manager** for OPENAI_API_KEY instead of environment variables
2. **Enable CloudTrail** for audit logs
3. **Use least-privilege IAM roles** (CDK creates these)
4. **Enable AWS WAF** on API Gateway for production
5. **Encrypt S3 buckets** (enabled by default in CDK stack)
6. **Rotate OAuth secrets** regularly
7. **Monitor CloudWatch alarms** for unusual activity
8. **Use VPC** if accessing private resources

## Cleanup

Delete all resources:

```bash
cd examples
cdk destroy

# Manually delete S3 bucket if retained
aws s3 rm s3://athenaeum-index-ACCOUNT --recursive
aws s3 rb s3://athenaeum-index-ACCOUNT
```

## Advanced Topics

### Custom Embedding Models

Use different HuggingFace models:

```python
# In your index build
athenaeum index ./docs \
  --embed-model "sentence-transformers/all-mpnet-base-v2" \
  --output ./index
```

### Multiple Environments

Deploy to different stages:

```bash
cdk deploy --context environment=dev
cdk deploy --context environment=prod
```

### VPC Integration

Access private resources:

```python
mcp_lambda = lambda_.Function(
    # ... other config ...
    vpc=vpc,
    vpc_subnets=ec2.SubnetSelection(
        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
    ),
)
```

### Custom Domains

Add API Gateway custom domain:

```python
from aws_cdk import aws_certificatemanager as acm

domain = apigateway.DomainName(
    self, "CustomDomain",
    domain_name="api.yourdomain.com",
    certificate=certificate,
)

api.add_domain_name_mapping("DomainMapping", domain_name=domain)
```

## Support & Resources

- **GitHub Issues**: Report bugs or request features
- **CloudWatch Logs**: Primary debugging tool
- **AWS CDK Docs**: https://docs.aws.amazon.com/cdk/
- **Lambda Web Adapter**: https://github.com/awslabs/aws-lambda-web-adapter
- **LlamaIndex Docs**: https://docs.llamaindex.ai/

## Recent Updates (Session Summary)

**Fixed in this session:**
1. ✅ CLI lazy imports - instant `--help` response
2. ✅ Renamed `query` → `chat`, added `search` command  
3. ✅ Changed default LLM to OpenAI gpt-4o-mini
4. ✅ Removed chunk truncation in search display
5. ✅ Optimized CDK bundling (two-layer strategy)
6. ✅ Fixed duplicate construct IDs in CDK
7. ✅ Corrected athenaeum installation path in bundling
8. ✅ Updated DEPLOYMENT.md with current best practices

**Key learnings:**
- Lazy imports: Move heavy imports inside command functions for better UX
- Two-layer bundling: Separate cached dependencies from fast-changing code
- Lambda Web Adapter: Official AWS solution, runs on port 8080
- Chunking strategies: Larger chunks (3072-4096) for narratives, smaller (2048) for rules
- Editable installs: `uv pip install -e ../athenaeum` for development
