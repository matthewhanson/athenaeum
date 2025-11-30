# AWS Lambda Deployment Guide

This guide covers deploying Athenaeum as a serverless Lambda function with OAuth authentication.

## Architecture

- **AWS Lambda**: Runs the FastAPI MCP server using Mangum adapter
- **API Gateway**: Provides HTTP endpoints with custom OAuth authorizer
- **S3**: Stores index files (if too large for Lambda)
- **Lambda Layer**: Contains heavy dependencies (PyTorch, FAISS, LlamaIndex)
- **OAuth Authorizer**: Validates JWT tokens from your OAuth provider

## Prerequisites

1. **AWS Account**: With appropriate permissions (Lambda, API Gateway, S3, IAM)
2. **AWS CLI**: Configured with credentials
   ```bash
   aws configure
   ```
3. **OAuth Provider**: Auth0, Cognito, Okta, or similar
   - You'll need: Issuer URL, Audience, JWKS URL

## Setup

### 1. Install Deployment Dependencies

```bash
cd athenaeum
uv sync --extra deploy
```

### 2. Configure OAuth

Copy the example context file and fill in your OAuth settings:

```bash
cp cdk.context.json.example cdk.context.json
```

Edit `cdk.context.json`:
```json
{
  "oauth_issuer": "https://your-oauth-provider.com",
  "oauth_audience": "your-api-audience",
  "oauth_jwks_url": "https://your-oauth-provider.com/.well-known/jwks.json"
}
```

**Common OAuth Providers:**

- **Auth0**: 
  - Issuer: `https://YOUR_DOMAIN.auth0.com/`
  - JWKS: `https://YOUR_DOMAIN.auth0.com/.well-known/jwks.json`
  
- **AWS Cognito**:
  - Issuer: `https://cognito-idp.REGION.amazonaws.com/USER_POOL_ID`
  - JWKS: `https://cognito-idp.REGION.amazonaws.com/USER_POOL_ID/.well-known/jwks.json`
  
- **Okta**:
  - Issuer: `https://YOUR_DOMAIN.okta.com/oauth2/default`
  - JWKS: `https://YOUR_DOMAIN.okta.com/oauth2/default/v1/keys`

### 3. Build Your Index

Before deploying, create your index locally:

```bash
# Convert PDFs to markdown
uv run athenaeum convert ./docs --out ./markdown

# Build index
uv run athenaeum index ./markdown --output ./index
```

The `index/` directory will be packaged with your Lambda deployment (if it fits) or uploaded to S3.

### 4. Deploy

Run the deployment script:

```bash
./deploy.sh
```

This will:
1. Bootstrap CDK (first time only)
2. Build Lambda layer with dependencies
3. Package your code and index
4. Deploy to AWS
5. Output your API endpoint URL

## Index Size Considerations

**Lambda Limits:**
- Deployment package: 50 MB (zipped), 250 MB (unzipped)
- With layers: 250 MB (unzipped)
- /tmp storage: 512 MB - 10 GB (configurable)

**Strategies:**

1. **Small indices (<200 MB)**: Package with Lambda layer
2. **Medium indices (200 MB - 10 GB)**: Store in S3, download to /tmp on cold start
3. **Large indices (>10 GB)**: Use EFS mount or consider ECS/Fargate instead

The CDK stack handles both strategies automatically:
- Attempts to include index in deployment
- Falls back to S3 + /tmp download if needed

## Usage

### Get Your API Endpoint

```bash
aws cloudformation describe-stacks \
  --stack-name AtheneumStack \
  --query 'Stacks[0].Outputs[?OutputKey==`APIEndpoint`].OutputValue' \
  --output text
```

### Make Authenticated Requests

1. **Get an access token** from your OAuth provider
2. **Call the API** with the token:

```bash
curl -X POST https://YOUR_API_ENDPOINT/search \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this about?", "top_k": 5}'
```

### Test Endpoints

```bash
# Health check (no auth required if you modify the stack)
curl https://YOUR_API_ENDPOINT/health

# List models
curl https://YOUR_API_ENDPOINT/models \
  -H "Authorization: Bearer YOUR_TOKEN"

# Search for documents
curl -X POST https://YOUR_API_ENDPOINT/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "search query", "top_k": 5}'

# Chat completion
curl -X POST https://YOUR_API_ENDPOINT/chat/completions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "athenaeum-index-retrieval",
    "messages": [{"role": "user", "content": "What is this about?"}],
    "max_tokens": 500
  }'
```

## Connecting to ChatGPT

### Option 1: Custom GPT with Actions

1. Go to ChatGPT → Create Custom GPT
2. Configure → Actions → Add Action
3. Set up authentication:
   - Type: Bearer Token
   - Token: Your OAuth access token
4. Add your API schema (OpenAPI/Swagger)
5. Test and publish

### Option 2: OpenAI Plugin (if available)

Create a plugin manifest pointing to your API endpoint.

### Option 3: Browser Extension

Use a browser extension that can inject custom API calls into ChatGPT with auth headers.

## Cost Estimation

**Monthly costs** (approximate, us-east-1):
- Lambda: $0.20 per 1M requests + compute time
- API Gateway: $1.00 per 1M requests
- S3: $0.023 per GB/month
- Data transfer: $0.09 per GB out

**Example:** 10K requests/month with 2GB index:
- ~$1-2 per month

## Monitoring

### CloudWatch Logs

View Lambda logs:
```bash
aws logs tail /aws/lambda/AtheneumStack-MCPServerFunction --follow
```

### Metrics

Monitor in CloudWatch:
- Lambda invocations
- Duration
- Errors
- API Gateway requests
- Authorizer failures

## Updating

To update your deployment:

1. **Update code**: Make changes to your source
2. **Update index**: Rebuild if needed
3. **Redeploy**:
   ```bash
   ./deploy.sh
   ```

## Cleanup

To delete all resources:

```bash
uv run cdk destroy
```

## Troubleshooting

### OAuth Issues

**"Unauthorized" errors:**
- Verify your token is valid: Check expiration
- Confirm issuer/audience match your OAuth provider
- Check JWKS URL is accessible
- View authorizer logs in CloudWatch

### Lambda Timeouts

- Increase timeout in `athenaeum_stack.py` (max 15 minutes)
- Consider using provisioned concurrency for faster cold starts
- Optimize index loading

### Out of Memory

- Increase memory size in `athenaeum_stack.py` (max 10 GB)
- Use smaller embedding models
- Reduce index size

### Index Not Loading

- Check S3 bucket permissions
- Verify index files uploaded correctly
- Check Lambda logs for download errors
- Ensure /tmp has enough space

## Advanced Configuration

### Custom Domain

Add a custom domain in `athenaeum_stack.py`:

```python
domain = apigateway.DomainName(
    self, "CustomDomain",
    domain_name="api.yourdomain.com",
    certificate=certificate,
)
```

### VPC Access

If you need to access resources in a VPC:

```python
mcp_lambda = lambda_.Function(
    # ... other config ...
    vpc=vpc,
    vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
)
```

### Multiple Environments

Deploy to different stages:

```bash
uv run cdk deploy --context environment=dev
uv run cdk deploy --context environment=prod
```

## Security Best Practices

1. **Rotate OAuth secrets** regularly
2. **Enable CloudTrail** for API access logs
3. **Use least-privilege IAM roles**
4. **Enable AWS WAF** for API Gateway if needed
5. **Encrypt S3 buckets** (enabled by default)
6. **Use Secrets Manager** for sensitive config
7. **Enable MFA** for AWS account
8. **Review CloudWatch alarms** for unusual activity

## Performance Optimization

1. **Use smaller models**: Choose efficient embedding models
2. **Optimize index**: Use FAISS IVF or HNSW indices for large datasets
3. **Enable provisioned concurrency**: For consistent latency
4. **Use Lambda SnapStart**: For faster cold starts (Java only currently)
5. **Cache embeddings**: Store and reuse where possible
6. **Batch requests**: If processing multiple documents

## Support

For issues:
1. Check CloudWatch logs
2. Review deployment output
3. Verify OAuth configuration
4. Test with curl before integrating
5. Open an issue on GitHub
