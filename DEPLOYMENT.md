# AWS Lambda Deployment Guide# AWS Lambda Deployment Guide



This guide covers deploying Athenaeum as a serverless Lambda function using AWS CDK with Docker container images.



## OverviewThis guide covers deploying Athenaeum as a serverless Lambda function using AWS CDK with Docker container images.



Athenaeum uses **Docker container images** for Lambda deployment to support the full ML stack including PyTorch and sentence-transformers for embeddings. Container images support up to 10GB (vs 250MB for layers), making them ideal for ML workloads.



**What you get:**## Overview

- Lambda function in Docker container (~2GB)

- FastAPI server with Lambda Web Adapter

- API Gateway REST API with CORS

- S3 bucket for vector index storageAthenaeum uses **Docker container images** for Lambda deployment to support the full ML stack including PyTorch and sentence-transformers for embeddings. Container images support up to 10GB (vs 250MB for layers), making them ideal for ML workloads.

- Automatic index download on cold start



## Architecture

**What you get:**

```

Client Request- Lambda function in Docker container (~2GB)

    ↓

API Gateway (REST API with CORS)- FastAPI server with Lambda Web Adapter

    ↓

Lambda Container (Docker)- API Gateway REST API with CORS

    ├── Lambda Web Adapter (converts APIGW → HTTP)

    ├── PyTorch (CPU-only, ~900MB)- S3 bucket for vector index storage

    ├── Transformers + sentence-transformers

    ├── LlamaIndex + FAISS- Automatic index download on cold start

    ├── FastAPI (athenaeum.mcp_server:app)

    └── Index loaded from S3 → /tmp/index

    ↓

S3 Bucket## Architecture

    └── Vector index files

```



## Prerequisites```



1. **AWS Account** with permissions for Lambda, API Gateway, S3, IAM, ECRClient Request

2. **AWS CLI** configured: `aws configure`

3. **AWS CDK**: `npm install -g aws-cdk`    ↓

4. **Docker** installed and running

5. **Python 3.12+**API Gateway (REST API with CORS)

6. **OpenAI API key** (or AWS Bedrock credentials)

    ↓

## Quick Start

Lambda Container (Docker)

### 1. Install Athenaeum

    ├── Lambda Web Adapter (converts APIGW → HTTP)

```bash

pip install athenaeum[deploy]    ├── PyTorch (CPU-only, ~900MB)

```

    ├── Transformers + sentence-transformers

### 2. Build Your Index

    ├── LlamaIndex + FAISS

```bash

athenaeum index /path/to/markdown/files --output ./index    ├── FastAPI (athenaeum.mcp_server:app)

```

    └── Index loaded from S3 → /tmp/index

### 3. Create CDK App

    ↓

```python

# app.pyS3 Bucket

from aws_cdk import App, Stack, CfnOutput, Duration

from athenaeum.infra import MCPServerContainerConstruct    └── Vector index files

import os

```

app = App()

stack = Stack(app, "MyKnowledgeBase")



# Deploy MCP server with container## Prerequisites

server = MCPServerContainerConstruct(

    stack, "Server",

    index_path="./index",  # Your vector index directory

    environment={1. **AWS Account** with permissions for Lambda, API Gateway, S3, IAM, ECR

        "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],

    },2. **AWS CLI** configured: `aws configure`

    memory_size=2048,  # 2GB recommended for ML workloads

    timeout=Duration.minutes(5),3. **AWS CDK**: `npm install -g aws-cdk`

)

4. **Docker** installed and running

CfnOutput(stack, "ApiUrl", value=server.api_url)

5. **Python 3.12+**

app.synth()

```6. **OpenAI API key** (or AWS Bedrock credentials)



### 4. Deploy



```bash## Quick Start

export OPENAI_API_KEY=sk-...

export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

export CDK_DEFAULT_REGION=us-east-1

### 1. Install Athenaeum

cdk deploy

```



## Building Your Index```bash



Create your vector index locally before deploying:pip install athenaeum[deploy]



```bash```

# Simple indexing

athenaeum index ./docs --output ./index



# Custom chunk sizes for different content types### 2. Build Your Index

# For documentation/guides (balanced)

athenaeum index ./docs \

  --output ./index \

  --chunk-size 2048 \```bash

  --chunk-overlap 400

athenaeum index /path/to/markdown/files --output ./index

# For narratives/timelines (larger chunks preserve context)

athenaeum index ./stories \```

  --output ./index \

  --chunk-size 3072 \

  --chunk-overlap 800

### 3. Create CDK App

# Exclude patterns

athenaeum index ./docs \

  --output ./index \

  --exclude "**/.git/**" "**/__pycache__/**" "**/*.png"```python

```

# app.py

**Chunking Strategy:**

- **Small docs (APIs, references)**: 1024 chunks, 200 overlapfrom aws_cdk import App, Stack, CfnOutput, Duration

- **Medium docs (guides, documentation)**: 2048 chunks, 400 overlap

- **Large docs (narratives, timelines)**: 3072-4096 chunks, 800 overlapfrom athenaeum.infra import MCPServerContainerConstruct

- **Overlap**: 20-30% of chunk size for continuity

import os

The `MarkdownNodeParser` automatically preserves heading hierarchy regardless of chunk size.



## Container Configuration

app = App()

### Custom Dockerfile

stack = Stack(app, "MyKnowledgeBase")

By default, the construct uses `athenaeum/examples/deployment/Dockerfile`. To customize:



```python

server = MCPServerContainerConstruct(# Deploy MCP server with container

    self, "Server",

    dockerfile_path="/path/to/custom/Dockerfile",server = MCPServerContainerConstruct(

    docker_build_context="/path/to/build/context",

    # ... other settings    stack, "Server",

)

```    index_path="./index",



### Environment Variables# Your vector index directory



Configure Lambda environment:    environment={



```python        "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],

server = MCPServerContainerConstruct(

    self, "Server",    },

    environment={

        # LLM provider    memory_size=2048,

        "OPENAI_API_KEY": "sk-...",  # Use Secrets Manager in production

        # 2GB recommended for ML workloads

        # Or use AWS Bedrock

        # "AWS_ACCESS_KEY_ID": "...",    timeout=Duration.minutes(5),

        # "AWS_SECRET_ACCESS_KEY": "...",

        )

        # Index location (set automatically by construct)

        # "INDEX_BUCKET": "...",

        # "INDEX_KEY": "index/",

    },CfnOutput(stack, "ApiUrl", value=server.api_url)

)

```



### Resource Configurationapp.synth()



Adjust based on your needs:```



```python

server = MCPServerContainerConstruct(

    self, "Server",### 4. Deploy

    memory_size=2048,  # MB (default: 2048, recommended for PyTorch)

    ephemeral_storage_size=512,  # MB (default: 512)

    timeout=Duration.minutes(5),  # Max: 15 minutes

)```bash

```

export OPENAI_API_KEY=sk-...

**Sizing Guidelines:**

- **Small indices (<500MB)**: 2048 MB memory, 512 MB storageexport CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

- **Medium indices (500MB-2GB)**: 3008 MB memory, 1024 MB storage

- **Large indices (2GB+)**: 4096 MB memory, 2048 MB storageexport CDK_DEFAULT_REGION=us-east-1



## Using Your API



### Get API Endpointcdk deploy



After deployment, CDK outputs the API URL:```



```bash

# From CDK output

API_URL=$(aws cloudformation describe-stacks \## Building Your Index### Benefits

  --stack-name MyKnowledgeBase \

  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \

  --output text)

```Create your vector index locally before deploying:- **~20 lines** instead of ~200



### Test Endpoints- **Best practices built-in**: CPU-only PyTorch, size optimization, proper IAM



**Health Check:**```bash- **Versioned API**: Constructs are semver'd with athenaeum package

```bash

curl $API_URL/health# Simple indexing- **No boilerplate**: All infrastructure logic encapsulated

```

athenaeum index ./docs --output ./index- **Fast rebuilds**: Cached dependencies layer

**Search (retrieval only, no LLM):**

```bash- **Flexible**: Use local source (dev) or published package (prod)

curl -X POST $API_URL/search \

  -H "Content-Type: application/json" \# Custom chunk sizes for different content types

  -d '{"query": "your search query", "limit": 5}'

```# For documentation/guides (balanced)### Example



**Chat (RAG with LLM response):**athenaeum index ./docs \

```bash

curl -X POST $API_URL/chat \  --output ./index \See `examples/simple-deployment/` for a complete working example.

  -H "Content-Type: application/json" \

  -d '{  --chunk-size 2048 \

    "question": "What is this documentation about?"

  }'  --chunk-overlap 400

```

## Deployment Approach 2: Custom CDK Stack

## Updating Your Deployment



### Update Application Code

# For narratives/timelines (larger chunks preserve context)For full control over infrastructure, you can write your own CDK stack. This approach gives you more flexibility but requires more code.

If you modify athenaeum source or deployment scripts:

athenaeum index ./stories \

```bash

cdk deploy  --output ./index \

```

### Installation

This rebuilds the Docker container and deploys the new image.

  --chunk-size 3072 \

### Update Index

  --chunk-overlap 800```bash

Rebuild and redeploy your index:

# Clone or navigate to athenaeum

```bash

# Rebuild index locally# Exclude patternscd athenaeum

athenaeum index ./docs --output ./index

athenaeum index ./docs \

# Deploy (auto-uploads to S3)

cdk deploy  --output ./index \

```

# Install with deployment extras

Or manually update S3:

  --exclude "

```bash

INDEX_BUCKET=$(aws cloudformation describe-stacks \**/.git/**" "**/__pycache__/**" "**/*.png"uv sync --extra deploy

  --stack-name MyKnowledgeBase \

  --query 'Stacks[0].Outputs[?OutputKey==`IndexBucketName`].OutputValue' \```

  --output text)

# Or with pip

aws s3 sync ./index s3://$INDEX_BUCKET/index/ --delete

```**Chunking Strategy:**pip install -e ".[deploy]"



## Local Development- **Small docs (APIs, references)**: 1024 chunks, 200 overlap```



### Test Container Locally- **Medium docs (guides, documentation)**: 2048 chunks, 400 overlap



Build and run the container on your machine:- **Large docs (narratives, timelines)**: 3072-4096 chunks, 800 overlap



```bash### Configure AWS CDK

# Build container

cd /path/to/athenaeum- **Overlap**: 20-30% of chunk size for continuity

docker build -f examples/deployment/Dockerfile -t athenaeum-lambda .

```bash

# Run locally

docker run -p 8080:8080 \The `MarkdownNodeParser` automatically preserves heading hierarchy regardless of chunk size.

  -e OPENAI_API_KEY=sk-... \

  -e INDEX_DIR=/tmp/index \# Set environment

  -v $(pwd)/index:/tmp/index \

  athenaeum-lambdaexport AWS_REGION=us-east-1



# Test## Container Configurationexport CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

curl http://localhost:8080/health

```export CDK_DEFAULT_REGION=$AWS_REGION



### Run MCP Server Locally### Custom Dockerfile



```bash# Bootstrap CDK (first time only)

# Set environment

export OPENAI_API_KEY=sk-...By default, the construct uses `athenaeum/examples/deployment/Dockerfile`. To customize:cdk bootstrap

export INDEX_DIR=./index

```

# Run server

athenaeum serve --index ./index --port 8000```python



# Or use uvicorn directlyserver = MCPServerContainerConstruct(

uvicorn athenaeum.mcp_server:app --reload --port 8000

```### Custom Stack Example



## Troubleshooting    self, "Server",



### Common Issues    dockerfile_path="/path/to/custom/Dockerfile",See `examples/simple-deployment/stacks/athenaeum_stack.py` for a full custom CDK stack implementation showing:



**1. Docker build fails**    docker_build_context="/path/to/build/context",- PyTorch CPU-only installation (avoids 7GB+ CUDA libraries)

- Ensure Docker daemon is running

- Check available disk space (PyTorch is large)

- Try `docker system prune` to free space

# ... other settings- Lambda layer size optimization (~1.2GB → ~300MB compressed)

**2. Lambda timeout**

- Increase timeout in construct)- Lambda Web Adapter integration

- Check CloudWatch logs for slow operations

- Consider increasing memory (faster CPU)```- S3 bucket for index storage



**3. Out of memory**- API Gateway with CORS

- Increase `memory_size` in construct

- PyTorch + model uses ~1GB, allow 2GB+ total### Environment Variables

- Check `ephemeral_storage_size` if index is large

## Building Your Index

**4. Index not loading**

- Verify S3 permissions (auto-configured by construct)Configure Lambda environment:

- Check CloudWatch logs for download errors

- Test locally first with same indexBefore deploying, create your index locally:



**5. Slow cold starts**```python

- Index download from S3 takes time (~10-20 seconds)

- Consider provisioned concurrency for critical workloadsserver = MCPServerContainerConstruct(```bash

- Use smaller indices or optimize chunk size

    self, "Server",

### Debugging

# Simple indexing

**View Lambda Logs:**

```bash    environment={athenaeum index ./docs --output ./index

aws logs tail /aws/lambda/MyKnowledgeBase-ServerFunction --follow

```



**Check Container Locally:**# LLM provider

```bash

# Build and run locally to debug        "OPENAI_API_KEY": "sk-...",

docker build -f examples/deployment/Dockerfile -t test .

docker run -p 8080:8080 test# Use Secrets Manager in production# Advanced: Custom chunk sizes for different content types



# Shell into container

docker run -it --entrypoint /bin/bash test

```# For RPG rules/mechanics (balanced)



**CDK Diagnostics:**

```bash

cdk diff  # See what would change# Or use AWS Bedrockathenaeum index ./rules \

cdk ls    # List all stacks

cdk synth # Generate CloudFormation template

```

# "AWS_ACCESS_KEY_ID": "...",  --output ./index \

## Cost Optimization



**Monthly cost estimates** (us-east-1):

# "AWS_SECRET_ACCESS_KEY": "...",  --chunk-size 2048 \

**Light usage** (~1,000 requests/month):

- Lambda: ~$1-2 (mostly cold starts)          --chunk-overlap 400

- API Gateway: ~$1

- S3: ~$0.50 (1GB index)

- ECR: ~$0.10 (2GB image)

- **Total: ~$2-4/month**# Index location (set automatically by construct)



**Medium usage** (~10,000 requests/month):

- Lambda: ~$5-10

- API Gateway: ~$3-5# "INDEX_BUCKET": "...",# For timelines/narratives (larger chunks preserve context)

- S3: ~$0.50

- ECR: ~$0.10

- **Total: ~$8-16/month**

# "INDEX_KEY": "index/",athenaeum index ./timelines \

**Optimization Tips:**

- Use CPU-only PyTorch (included in Dockerfile)    },  --output ./index \

- Enable API Gateway response caching

- Use smaller embedding models if acceptable)  --chunk-size 3072 \

- Clean up old ECR images: `aws ecr batch-delete-image`

- Use S3 Intelligent-Tiering for large indices```  --chunk-overlap 800



## Security Best Practices



1. **Use AWS Secrets Manager** for API keys instead of environment variables:### Resource Configuration# Exclude patterns

```python

from aws_cdk import aws_secretsmanager as secretsmanagerathenaeum index ./docs \



secret = secretsmanager.Secret.from_secret_name(Adjust based on your needs:  --output ./index \

    self, "ApiKey",

    secret_name="openai-api-key"  --exclude "

)

**/.git/**" "**/__pycache__/**" "**/*.png"

server = MCPServerContainerConstruct(

    self, "Server",```python```

    environment={

        "OPENAI_API_KEY": secret.secret_value.to_string(),server = MCPServerContainerConstruct(

    },

)    self, "Server",

secret.grant_read(server.function)

```**Chunking Strategy:**



2. **Enable CloudTrail** for audit logs    memory_size=2048,

3. **Use least-privilege IAM roles** (auto-configured by construct)

4. **Enable AWS WAF** on API Gateway for production# MB (default: 2048, recommended for PyTorch)- **Small docs (APIs, references)**: 1024 chunks, 200 overlap

5. **Encrypt S3 buckets** (enabled by default)

6. **Monitor CloudWatch alarms** for unusual activity    ephemeral_storage_size=512,

7. **Use VPC** if accessing private resources

# MB (default: 512)- **Medium docs (guides, rules)**: 2048-3072 chunks, 400-600 overlap

## Advanced Configuration

    timeout=Duration.minutes(5),

### Multiple Environments

# Max: 15 minutes- **Large docs (narratives)**: 3072-4096 chunks, 800-1200 overlap

Deploy to different stages:

)- **Overlap**: 20-30% of chunk size for continuity

```python

env_name = app.node.try_get_context("environment") or "dev"```



server = MCPServerContainerConstruct(The `MarkdownNodeParser` automatically preserves heading hierarchy regardless of chunk size.

    self, f"Server-{env_name}",

    # ... config**Sizing Guidelines:**

)

```- **Small indices (<500MB)**: 2048 MB memory, 512 MB storage



```bash## CDK Stack Architecture

cdk deploy --context environment=dev

cdk deploy --context environment=prod- **Medium indices (500MB-2GB)**: 3008 MB memory, 1024 MB storage

```

- **Large indices (2GB+)**: 4096 MB memory, 2048 MB storage

### VPC Integration

### Two-Layer Bundling Strategy

Access private resources:



```python

from aws_cdk import aws_ec2 as ec2## Using Your API



# Use existing VPC**Problem:** Bundling everything together made deploys slow (5+ minutes every time)

vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id="vpc-...")



# Modify construct to support VPC (requires extending MCPServerContainerConstruct)

```### Get API Endpoint



### Custom Domain**Solution:** Separate cached dependencies from fast-changing code



Add API Gateway custom domain:



```pythonAfter deployment, CDK outputs the API URL:

from aws_cdk import aws_certificatemanager as acm

from aws_cdk import aws_apigateway as apigateway**Dependencies Layer** (slow, cached):



certificate = acm.Certificate.from_certificate_arn(- Bundles athenaeum package + all PyPI dependencies

    self, "Cert",

    certificate_arn="arn:aws:acm:..."```bash- Only rebuilds when `requirements.txt` or athenaeum source changes

)

# From CDK output- Uses Docker bundling in CDK for consistent Linux builds

domain = apigateway.DomainName(

    self, "CustomDomain",API_URL=$(aws cloudformation describe-stacks \- Size: ~200-400 MB (includes PyTorch, FAISS, LlamaIndex)

    domain_name="api.yourdomain.com",

    certificate=certificate,  --stack-name MyKnowledgeBase \

)

  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \

# Map to API

server.api.add_domain_name_mapping("Mapping", domain_name=domain)**Function Layer** (fast, rebuilds every time):

```

  --output text)- Just deployment scripts (`lambda_handler.py`, `oauth_authorizer.py`)

### Provisioned Concurrency

```- Creates `run.sh` script for Lambda Web Adapter

Keep instances warm to avoid cold starts:

- Rebuilds in seconds

```python

# Note: This requires extending the construct or using alias### Test Endpoints- Size: < 1 MB

# Adds ~$14/month per GB-hour provisioned

alias = server.function.add_alias(

    "live",

    provisioned_concurrent_executions=1,**Health Check:**

)

```### Example CDK Stack



## Cleanup```bash



Delete all resources:curl $API_URL/healthSee `examples/cdk/stacks/athenaeum_stack.py` for the complete example. Key points:



```bash```

cdk destroy

```python

# Manually delete S3 bucket if retained

aws s3 rm s3://my-knowledge-base-index-ACCOUNT --recursive**Search (retrieval only, no LLM):**

aws s3 rb s3://my-knowledge-base-index-ACCOUNT

# Dependencies layer - cached

# Delete ECR images

aws ecr batch-delete-image \```bashdependencies_layer = lambda_.LayerVersion(

  --repository-name my-knowledge-base-server \

  --image-ids imageTag=latestcurl -X POST $API_URL/search \    code=lambda_.Code.from_asset(

```

  -H "Content-Type: application/json" \        str(project_root.parent),

## Performance Considerations

# Access parent to get athenaeum package

### Cold Start Times

- **First request**: 10-20 seconds (loading PyTorch + downloading index)  -d '{"query": "your search query", "limit": 5}'        bundling={

- **Warm requests**: 1-2 seconds (model already loaded)

- **Provisioned concurrency**: Sub-second (always warm)```            "command": [



### Memory vs Cost                "pip install -r requirements.txt -t /asset-output/python",

- More memory = faster CPU = faster processing

- 2GB is sweet spot for PyTorch workloads**Chat (RAG with LLM response):**                "pip install /asset-input/athenaeum -t /asset-output/python",

- Monitor CloudWatch metrics to optimize

```bash            ]

### Container Image Size

- Current: ~2GB (PyTorch CPU + dependencies)curl -X POST $API_URL/chat \        }

- Well under 10GB limit

- Docker layer caching speeds up rebuilds  -H "Content-Type: application/json" \    )



## Support & Resources  -d '{)



- **Examples**: See `examples/deployment/` for complete working example    "question": "What is this documentation about?"

- **GitHub Issues**: Report bugs or request features

- **CloudWatch Logs**: Primary debugging tool  }'

- **AWS CDK Docs**: https://docs.aws.amazon.com/cdk/

- **Lambda Container Images**: https://docs.aws.amazon.com/lambda/latest/dg/images-create.html# Function layer - fast rebuilds

- **Lambda Web Adapter**: https://github.com/awslabs/aws-lambda-web-adapter

```mcp_lambda = lambda_.Function(

    code=lambda_.Code.from_asset(

## Updating Your Deployment        str(project_root / "deployment"),

        bundling={

### Update Application Code            "command": [

                "cp lambda_handler.py /asset-output/",

If you modify athenaeum source or deployment scripts:                "echo 'exec uvicorn athenaeum.mcp_server:app ...' > /asset-output/run.sh",

            ]

```bash        }

cdk deploy    ),

```    layers=[dependencies_layer, web_adapter_layer]

)

This rebuilds the Docker container and deploys the new image.```



### Update Index## Usage



Rebuild and redeploy your index:

### Get Your API Endpoint



```bash

# Rebuild index locallyaws cloudformation describe-stacks \

athenaeum index ./docs --output ./index  --stack-name AtheneumStack \

  --query 'Stacks[0].Outputs[?OutputKey==`APIEndpoint`].OutputValue' \

# Deploy (auto-uploads to S3)  --output text

cdk deploy```

```

### Test Endpoints

Or manually update S3:

**Without OAuth (public access):**

```bash

INDEX_BUCKET=$(aws cloudformation describe-stacks \```bash

  --stack-name MyKnowledgeBase \

# Health check

  --query 'Stacks[0].Outputs[?OutputKey==`IndexBucketName`].OutputValue' \curl https://YOUR_API_ENDPOINT/health

  --output text)

# Search (retrieval only, no LLM)

aws s3 sync ./index s3://$INDEX_BUCKET/index/ --deletecurl -X POST https://YOUR_API_ENDPOINT/search \

```  -H "Content-Type: application/json" \

  -d '{"query": "your search query", "limit": 5}'

## Local Development

# Chat (RAG with LLM response)

### Test Container Locallycurl -X POST https://YOUR_API_ENDPOINT/chat/completions \

  -H "Content-Type: application/json" \

Build and run the container on your machine:  -d '{

    "model": "gpt-4o-mini",

```bash    "messages": [{"role": "user", "content": "What is this documentation about?"}]

# Build container  }'

cd /path/to/athenaeum```

docker build -f examples/deployment/Dockerfile -t athenaeum-lambda .

**With OAuth (requires token):**

# Run locally

docker run -p 8080:8080 \```bash

  -e OPENAI_API_KEY=sk-... \

# Get access token from your OAuth provider first

  -e INDEX_DIR=/tmp/index \TOKEN="eyJhbGc..."

  -v $(pwd)/index:/tmp/index \

  athenaeum-lambda

# Then add Authorization header

curl -X POST https://YOUR_API_ENDPOINT/search \

# Test  -H "Authorization: Bearer $TOKEN" \

curl http://localhost:8080/health  -H "Content-Type: application/json" \

```  -d '{"query": "your query", "limit": 5}'

```

### Run MCP Server Locally

## Updating Your Deployment

```bash

# Set environment### Fast Iteration with --hotswap

export OPENAI_API_KEY=sk-...

export INDEX_DIR=./indexWhen making frequent changes to Lambda **function code only** (not dependencies, infrastructure, or IAM), use `--hotswap` for much faster deployments:



# Run server```bash

athenaeum serve --index ./index --port 8000

# Standard deployment: 2-3 minutes (full CloudFormation update)

cdk deploy

# Or use uvicorn directly

uvicorn athenaeum.mcp_server:app --reload --port 8000

# Hotswap deployment: 10-30 seconds (bypasses CloudFormation)

```cdk deploy --hotswap

```

## Troubleshooting

**What --hotswap does:**

### Common Issues

1. **Detects code-only changes**: Compares your local changes against deployed stack

**1. Docker build fails**2. **Bypasses CloudFormation**: Directly updates Lambda via AWS SDK (`UpdateFunctionCode` API)

- Ensure Docker daemon is running3. **Skips changeset creation**: No waiting for CloudFormation to plan/execute

- Check available disk space (PyTorch is large)4. **Updates immediately**: New code is live in seconds instead of minutes

- Try `docker system prune` to free space

**What --hotswap does NOT do:**

**2. Lambda timeout**

- Increase timeout in construct- ❌ Update dependencies layer (requires full `cdk deploy`)

- Check CloudWatch logs for slow operations- ❌ Change infrastructure (API Gateway, S3, IAM, etc.)

- Consider increasing memory (faster CPU)- ❌ Modify environment variables

- ❌ Update resource configurations (memory, timeout, etc.)

**3. Out of memory**

- Increase `memory_size` in construct

**When to use --hotswap:**

- PyTorch + model uses ~1GB, allow 2GB+ total

- Check `ephemeral_storage_size` if index is large- ✅ Fixing bugs in `lambda_handler.py` or `athenaeum/` source code

- ✅ Tweaking FastAPI routes or response formatting

**4. Index not loading**- ✅ Adjusting LLM prompts or retrieval logic

- Verify S3 permissions (auto-configured by construct)- ✅ Rapid development/testing cycles

- Check CloudWatch logs for download errors

- Test locally first with same index

**When to use full `cdk deploy`:**



**5. Slow cold starts**- 🔄 Updated `requirements.txt` (new packages or versions)

- Index download from S3 takes time (~10-20 seconds)- 🔄 Changed Lambda memory, timeout, or other settings

- Consider provisioned concurrency for critical workloads- 🔄 Modified environment variables

- Use smaller indices or optimize chunk size- 🔄 Infrastructure changes (new API routes, S3 buckets, etc.)



### Debugging

**Safety Notes:**



**View Lambda Logs:**- `--hotswap` is **development-only** - never use in production CI/CD pipelines

```bash- Falls back to full deployment if infrastructure changes detected

aws logs tail /aws/lambda/MyKnowledgeBase-ServerFunction --follow- CloudFormation drift: Your stack's actual state diverges from template until next full deploy

```- Always do a final `cdk deploy` (without --hotswap) before production



**Check Container Locally:****Typical Workflow:**

```bash

# Build and run locally to debug```bash

docker build -f examples/deployment/Dockerfile -t test .

# 1. Initial deployment (full)

docker run -p 8080:8080 testcdk deploy



# Shell into container# 2. Fix bug in lambda_handler.py

docker run -it --entrypoint /bin/bash test

# Edit code...

```cdk deploy --hotswap

# 15 seconds



**CDK Diagnostics:**

# 3. Test, find another issue

```bash

# Edit code...

cdk diff

# See what would changecdk deploy --hotswap  # 15 seconds

cdk ls

# List all stacks

cdk synth

# Generate CloudFormation template# 4. Update requirements.txt (need new package)

```

# Edit requirements.txt...

cdk deploy

# 2-3 minutes (full - rebuilds dependencies layer)

## Cost Optimization

# 5. More code tweaks

**Monthly cost estimates** (us-east-1):

# Edit code...

cdk deploy --hotswap

# 15 seconds

**Light usage** (~1,000 requests/month):

- Lambda: ~$1-2 (mostly cold starts)

# 6. Ready to merge? Final full deployment

- API Gateway: ~$1cdk deploy

# Ensures CloudFormation state is correct

- S3: ~$0.50 (1GB index)```

- ECR: ~$0.10 (2GB image)

- **Total: ~$2-4/month**

### Update Scenarios



**Medium usage** (~10,000 requests/month):**Scenario 1: Code-only changes (use --hotswap)**

- Lambda: ~$5-10```bash

- API Gateway: ~$3-5

# Made changes to athenaeum source code or lambda_handler.py

- S3: ~$0.50cdk deploy --hotswap

- ECR: ~$0.10```

- **Total: ~$8-16/month**

**Scenario 2: Dependency changes (full deploy required)**

**Optimization Tips:**```bash

- Use CPU-only PyTorch (included in Dockerfile)

# Updated requirements.txt or athenaeum package version

- Enable API Gateway response caching

# Dependencies layer will rebuild (~2-3 min first time, then cached)

- Use smaller embedding models if acceptablecdk deploy

- Clean up old ECR images: `aws ecr batch-delete-image````

- Use S3 Intelligent-Tiering for large indices

**Scenario 3: Infrastructure changes (full deploy required)**

## Security Best Practices```bash

# Changed Lambda memory, added environment variables, modified IAM, etc.

1. **Use AWS Secrets Manager** for API keys instead of environment variables:cdk deploy

```python```

from aws_cdk import aws_secretsmanager as secretsmanager

### Update Index

secret = secretsmanager.Secret.from_secret_name(

    self, "ApiKey",```bash

    secret_name="openai-api-key"

# Rebuild index locally

)athenaeum index ./docs --output ./index



server = MCPServerContainerConstruct(

# Deploy (CDK auto-uploads to S3 if index/ exists)

    self, "Server",cd examples

    environment={cdk deploy --hotswap

        "OPENAI_API_KEY": secret.secret_value.to_string(),

    },

# Or manually sync to S3

)INDEX_BUCKET=$(aws cloudformation describe-stacks \

secret.grant_read(server.function)  --stack-name AtheneumStack \

```  --query 'Stacks[0].Outputs[?OutputKey==`IndexBucketName`].OutputValue' \

  --output text)

2. **Enable CloudTrail** for audit logsaws s3 sync ./index s3://$INDEX_BUCKET/index/ --delete

3. **Use least-privilege IAM roles** (auto-configured by construct)```

4. **Enable AWS WAF** on API Gateway for production

5. **Encrypt S3 buckets** (enabled by default)

## Local Development

6. **Monitor CloudWatch alarms** for unusual activity

7. **Use VPC** if accessing private resources

### CLI Usage



## Advanced ConfigurationThe athenaeum CLI is now optimized with lazy imports:



### Multiple Environments```bash

# Instant help (< 0.1s with lazy imports)

Deploy to different stages:athenaeum --help



```python

# Build index

env_name = app.node.try_get_context("environment") or "dev"athenaeum index ./docs --output ./index



server = MCPServerContainerConstruct(

# Search without LLM

    self, f"Server-{env_name}",athenaeum search "your query" --output ./index --top-k 5



# ... config

)

# Chat with LLM (uses OpenAI by default)

```athenaeum chat "your question" --output ./index



```bash

# Use Ollama instead

cdk deploy --context environment=devathenaeum chat "your question" \

cdk deploy --context environment=prod  --llm-provider ollama \

```  --llm-model llama3.1:8b

```

### VPC Integration

### MCP Server Locally

Access private resources:

```bash

```python

# Set environment

from aws_cdk import aws_ec2 as ec2export OPENAI_API_KEY=sk-...

export ATHENAEUM_INDEX_DIR=./index

# Use existing VPC

vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id="vpc-...")

# Run server

athenaeum serve --index ./index --port 8000

# Modify construct to support VPC (requires extending MCPServerContainerConstruct)

```

# Or use uvicorn directly

uvicorn athenaeum.mcp_server:app --reload --port 8000

### Custom Domain```



Add API Gateway custom domain:

## Lambda Configuration



```python

### Environment Variables

from aws_cdk import aws_certificatemanager as acm

from aws_cdk import aws_apigateway as apigatewaySet in Lambda console or via CDK:



certificate = acm.Certificate.from_certificate_arn(```python

    self, "Cert",environment={

    certificate_arn="arn:aws:acm:..."

# Required

)    "ATHENAEUM_INDEX_BUCKET": "your-bucket-name",

    "ATHENAEUM_INDEX_DIR": "/tmp/index",

domain = apigateway.DomainName(

    self, "CustomDomain",

# OpenAI (recommended for production)

    domain_name="api.yourdomain.com",    "OPENAI_API_KEY": "sk-...",

# Use Secrets Manager in production

    certificate=certificate,

)

# OAuth (if enabled)

    "OAUTH_ISSUER": "https://...",

# Map to API    "OAUTH_AUDIENCE": "...",

server.api.add_domain_name_mapping("Mapping", domain_name=domain)

```

# Lambda Web Adapter

    "AWS_LWA_INVOKE_MODE": "response_stream",

### Provisioned Concurrency    "AWS_LWA_PORT": "8080",

}

Keep instances warm to avoid cold starts:```



```python

### Resource Limits

# Note: This requires extending the construct or using alias

# Adds ~$14/month per GB-hour provisionedAdjust based on your index size and query complexity:

alias = server.function.add_alias(

    "live",```python

    provisioned_concurrent_executions=1,

# Small indices (<500MB)

)memory_size=1024

# MB

```timeout=30

# seconds



## Cleanup# Medium indices (500MB-2GB)

memory_size=2048

Delete all resources:timeout=60



```bash

# Large indices (2GB+) or complex queries

cdk destroymemory_size=3008

# Up to 10,240

timeout=120

# Up to 900 (15 minutes)

# Manually delete S3 bucket if retained```

aws s3 rm s3://my-knowledge-base-index-ACCOUNT --recursive

aws s3 rb s3://my-knowledge-base-index-ACCOUNT

## Troubleshooting



# Delete ECR images### Common Issues

aws ecr batch-delete-image \

  --repository-name my-knowledge-base-server \

**1. Lambda Timeout**

  --image-ids imageTag=latest- Increase timeout in CDK stack

```- Check index download time (large indices from S3)

- Monitor CloudWatch logs for bottlenecks

## Performance Considerations

**2. Out of Memory**

### Cold Start Times- Increase Lambda memory allocation

- **First request**: 10-20 seconds (loading PyTorch + downloading index)- Use smaller embedding models

- **Warm requests**: 1-2 seconds (model already loaded)- Reduce chunk size or number of chunks loaded

- **Provisioned concurrency**: Sub-second (always warm)

**3. OAuth "Unauthorized"**

### Memory vs Cost- Verify token hasn't expired

- More memory = faster CPU = faster processing- Check issuer/audience match exactly

- 2GB is sweet spot for PyTorch workloads- Ensure JWKS URL is accessible from Lambda

- Monitor CloudWatch metrics to optimize- Review authorizer CloudWatch logs



### Container Image Size

**4. Index Not Loading**

- Current: ~2GB (PyTorch CPU + dependencies)- Verify S3 bucket permissions (CDK creates these automatically)

- Well under 10GB limit- Check index files uploaded: `aws s3 ls s3://BUCKET/index/`

- Docker layer caching speeds up rebuilds- Review Lambda logs: `aws logs tail /aws/lambda/FUNCTION_NAME --follow`



## Support & Resources

**5. Slow Cold Starts**

- Index download from S3 takes time (proportional to size)

- **Examples**: See `examples/deployment/` for complete working example- Consider provisioned concurrency for critical workloads

- **GitHub Issues**: Report bugs or request features- Use smaller indices or Lambda SnapStart when available for Python

- **CloudWatch Logs**: Primary debugging tool

- **AWS CDK Docs**: https://docs.aws.amazon.com/cdk/

### Debugging

- **Lambda Container Images**: https://docs.aws.amazon.com/lambda/latest/dg/images-create.html

- **Lambda Web Adapter**: https://github.com/awslabs/aws-lambda-web-adapter**View Lambda Logs:**

```bash
aws logs tail /aws/lambda/AtheneumStack-MCPServerFunction --follow
```

**Check Stack Status:**
```bash
cdk diff

# See what would change
cdk ls

# List all stacks
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
