# Deployment Examples

This directory contains **example** deployment configurations. Copy and customize for your specific use case.

## Directory Structure

```
examples/
├── deployment/           # Lambda handler and authorizer
├── cdk/                  # AWS CDK infrastructure code
├── cdk.json             # CDK configuration
└── deploy.sh            # Deployment script
```

## Using These Examples

### For a New Project (like Nomikos)

1. **Copy to your project:**
   ```bash
   cp -r examples/deployment/ ../your-project/
   cp -r examples/cdk/ ../your-project/
   cp examples/cdk.json ../your-project/
   ```

2. **Customize the CDK stack:**
   - Update stack name (e.g., "AtheneumStack" → "NomikosStack")
   - Update bucket names (e.g., `athenaeum-index` → `nomikos-index`)
   - Update environment variables
   - Adjust Lambda settings (memory, timeout, etc.)

3. **Update cdk/app.py:**
   - Import your renamed stack
   - Update stack name and description

4. **Deploy:**
   ```bash
   cd your-project
   export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
   export CDK_DEFAULT_REGION=us-east-1
   cdk bootstrap  # First time only
   cdk deploy
   ```

## What You Need to Customize

### Lambda Handler (`deployment/lambda_handler.py`)
- `ATHENAEUM_INDEX_BUCKET` → Your bucket name
- `ATHENAEUM_INDEX_DIR` → Your index path

### CDK Stack (`cdk/stacks/athenaeum_stack.py`)
- Class name: `AtheneumStack` → `YourStack`
- Bucket name: `athenaeum-index-{account}` → `your-app-index-{account}`
- Stack description
- Environment variables
- Resource names/IDs

### CDK App (`cdk/app.py`)
- Import statement
- Stack name
- Description

### OAuth (if using)
Set context in `cdk.json`:
```json
{
  "context": {
    "oauth_issuer": "https://your-issuer.com",
    "oauth_audience": "your-audience",
    "oauth_jwks_url": "https://your-issuer.com/.well-known/jwks.json"
  }
}
```

## Local Testing

Before deploying, test locally:

```bash
# Build index
athenaeum index /path/to/markdown --output ./index

# Run FastAPI locally
export ATHENAEUM_INDEX_DIR=./index
uvicorn athenaeum.mcp_server:app --reload
```

## Architecture

```
API Gateway (with OAuth)
    ↓
Lambda Function (Python 3.12)
    ↓
S3 Bucket (index files)
```

The Lambda function:
1. Downloads index from S3 on cold start
2. Serves FastAPI via Lambda Web Adapter
3. Handles RAG queries using athenaeum library

## Cost Estimates

**Development:**
- Lambda: Free tier (1M requests/month)
- S3: ~$0.023/GB/month
- API Gateway: Free tier (1M requests/month)

**Production (light usage):**
- ~$5-10/month for typical use

## Next Steps

See specific project examples:
- **Nomikos**: RPG documentation knowledge base (coming soon)
- **Your Project**: Copy and customize these templates
