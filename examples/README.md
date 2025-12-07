# Athenaeum Examples

Example deployment configurations and reference implementations for Athenaeum.

## Directory Structure

```text
examples/
├── deployment/          # Lambda container deployment template
│   ├── Dockerfile       # Example Dockerfile for Lambda
│   ├── requirements.txt # Lambda dependencies
│   ├── run.sh          # Lambda Web Adapter startup
│   └── README.md       # Complete deployment guide
└── simple-deployment/   # (If exists) Simplified deployment example
```

## Quick Links

- **[deployment/](deployment/)** - Complete Lambda container deployment template
  - Docker container image approach (recommended for ML workloads)
  - Supports PyTorch + full ML stack
  - Reference Dockerfile and deployment guide
  - See [deployment/README.md](deployment/README.md) for complete instructions

## Using These Examples

### For Your Own Application

**Recommended approach:** Copy the deployment template and customize:

```bash
# Copy deployment template to your project
cp -r athenaeum/examples/deployment ./deployment

# Customize your Dockerfile to include your index
cat >> Dockerfile <<'EOF'
# Bake your index into the image
COPY index/ /var/task/index
EOF
```

**See `deployment/README.md` for complete template documentation and examples.**

### Structure Your Application

```text
your-application/
├── Dockerfile           # Based on examples/deployment/Dockerfile
├── deployment/
│   ├── requirements.txt
│   └── run.sh
├── index/              # Your vector index (baked into image)
└── cdk/
    └── app.py          # CDK deployment
```

## Deployment Approaches

### 1. Baked-In Index (Recommended)

Index is included in the Docker image:

- ✅ Zero cold start latency
- ✅ No S3 bucket needed
- ✅ Simpler architecture
- ✅ Lower costs

See [deployment/README.md](deployment/README.md) for details.

### 2. S3 Download (Legacy)

Index downloaded from S3 on cold start:

- ⚠️ Slower cold starts (5-30s)
- ⚠️ Requires S3 bucket + IAM
- ⚠️ More complex

Only use if index is too large (>8GB) for container images.

## Quick Start

1. **Build your index:**

   ```bash
   athenaeum index ./docs --output ./index
   ```

2. **Copy and customize template:**

   ```bash
   cp -r examples/deployment ./
   # Edit Dockerfile to add your index
   ```

3. **Deploy with CDK:**

   ```python
   from athenaeum.infra import MCPServerContainerConstruct

   server = MCPServerContainerConstruct(
       stack, "Server",
       dockerfile_path="./Dockerfile",
       docker_build_context=".",
       index_path=None,  # Baked into image
       environment={"OPENAI_API_KEY": os.environ["OPENAI_API_KEY"]},
   )
   ```

## Further Reading

- [deployment/README.md](deployment/README.md) - Complete deployment guide
- [Main README.md](../README.md) - Athenaeum overview and usage
- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
