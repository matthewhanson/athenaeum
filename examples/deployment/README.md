# Athenaeum Lambda Container Deployment

This directory contains files for deploying Athenaeum as an AWS Lambda function using Docker container images.

## Why Container Images?

Lambda container images support up to 10GB, allowing us to include:
- **PyTorch** (CPU-only, ~900MB)
- **Transformers** and **sentence-transformers** for embeddings
- **FAISS** for vector search
- Full **Athenaeum** package with all dependencies

Standard Lambda layers have a 250MB unzipped limit, which is insufficient for PyTorch.

## Files

- **Dockerfile** - Multi-stage build for Lambda container with PyTorch
- **requirements.txt** - Python dependencies for the container
- **lambda_handler.py** - Handler for downloading index from S3 on cold start
- **run.sh** - Startup script for Lambda Web Adapter
- **oauth_authorizer.py** - Optional OAuth/JWT authorizer for API Gateway

## Architecture

```
User Request
    ↓
API Gateway (with CORS)
    ↓
Lambda Container (Docker)
    ├── Lambda Web Adapter (converts APIGW → HTTP)
    ├── uvicorn (ASGI server)
    ├── FastAPI (athenaeum.mcp_server:app)
    └── Index loaded from S3 → /tmp/index
```

## Environment Variables

Required in Lambda:
- `OPENAI_API_KEY` - For LLM chat (or use AWS Bedrock)
- `INDEX_BUCKET` - S3 bucket containing the index (optional, set by CDK)
- `INDEX_KEY` - S3 key prefix for index files (optional, set by CDK)

Optional:
- `PORT` - Port for uvicorn (default: 8080)
- `AWS_LWA_INVOKE_MODE` - Lambda Web Adapter mode (default: response_stream)

## CDK Usage

### Using MCPServerContainerConstruct

```python
from aws_cdk import Stack
from athenaeum.infra import MCPServerContainerConstruct
import os

class MyStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        server = MCPServerContainerConstruct(
            self, "AthenaeumServer",
            # Optional: custom Dockerfile
            # dockerfile_path="/path/to/custom/Dockerfile",
            # docker_build_context="/path/to/athenaeum",
            
            # Index will be uploaded to S3 and downloaded on Lambda cold start
            index_path="/path/to/your/index",
            
            # Environment variables
            environment={
                "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
            },
            
            # Lambda configuration
            memory_size=2048,  # 2GB for ML workloads
            timeout=Duration.minutes(5),
        )
        
        # Output the API URL
        CfnOutput(self, "ApiUrl", value=server.api_url)
```

### Building Locally

To test the Docker build locally:

```bash
cd /path/to/athenaeum
docker build -f examples/deployment/Dockerfile -t athenaeum-lambda .
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=your-key \
  -e INDEX_DIR=/var/task/index \
  athenaeum-lambda
```

## Deployment

1. **Set up your index**:
   ```bash
   athenaeum index /path/to/markdown/files --output /path/to/index
   ```

2. **Configure environment**:
   ```bash
   export OPENAI_API_KEY=sk-...
   export CDK_DEFAULT_ACCOUNT=123456789012
   export CDK_DEFAULT_REGION=us-east-1
   ```

3. **Deploy with CDK**:
   ```bash
   cd your-cdk-project
   cdk deploy
   ```

4. **Test the endpoint**:
   ```bash
   curl -X POST https://your-api-url/chat \
     -H "Content-Type: application/json" \
     -d '{"question": "What is this knowledge base about?"}'
   ```

## Cost Considerations

- **Lambda**: Pay per request + duration (GB-seconds)
  - 2GB memory, 5-minute timeout max
  - Cold start: ~10-20 seconds (loading PyTorch + index)
  - Warm requests: ~1-2 seconds
  
- **S3**: Storage for index (typically < 100MB)
  - Negligible cost for small indexes
  
- **API Gateway**: Pay per request
  - Free tier: 1M requests/month

- **OpenAI API**: Pay per token
  - gpt-4o-mini: ~$0.15 per 1M input tokens

**Optimization Tips**:
- Use provisioned concurrency to avoid cold starts (costs more but faster)
- Cache frequently asked questions in DynamoDB
- Use reserved Lambda concurrency to control costs

## Troubleshooting

### Container build fails
- Check Docker daemon is running
- Ensure sufficient disk space (PyTorch is large)
- Try `docker system prune` to free space

### Lambda timeout
- Increase timeout in construct (max 15 minutes)
- Check CloudWatch logs for slow operations
- Consider increasing memory (faster CPU)

### Out of memory
- Increase memory_size in construct
- PyTorch CPU uses ~1GB, allow 2GB+ total
- Check ephemeral_storage_size if index is large

### Index not found
- Verify INDEX_BUCKET and INDEX_KEY are set
- Check S3 bucket permissions
- Review CloudWatch logs for download errors

## Migration from Layer-Based Deployment

If you were using `MCPServerConstruct` with `DependenciesLayerConstruct`:

**Before**:
```python
deps = DependenciesLayerConstruct(self, "Deps", ...)
server = MCPServerConstruct(self, "Server", dependencies_layer=deps.layer, ...)
```

**After**:
```python
server = MCPServerContainerConstruct(self, "Server", ...)
```

The container-based approach is simpler and supports the full dependency stack.
