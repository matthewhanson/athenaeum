# Athenaeum

[![PyPI - Version](https://img.shields.io/pypi/v/athenaeum)](https://pypi.org/project/athenaeum/)
[![Python Version](https://img.shields.io/pypi/pyversions/athenaeum)](https://pypi.org/project/athenaeum/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

*Give your LLM a library.*

A RAG (Retrieval-Augmented Generation) system built with LlamaIndex and FastAPI that provides both REST API and Model Context Protocol (MCP) interfaces for document retrieval and question answering.

## Features

- **Markdown-Focused**: Optimized for indexing markdown documents with structure-aware parsing
- **Vector Search**: FAISS-backed vector search using HuggingFace embeddings
- **Dual Interface**: REST API for web UIs and MCP protocol (SSE) for GitHub Copilot integration
- **CLI Tools**: Build indices, query, and run the server
- **AWS Lambda Deployment**: Serverless deployment with CDK, OAuth authentication, and S3 index storage
- **Reusable CDK Constructs**: L3 constructs for dependencies layer and MCP server deployment
- **Well-Tested**: Comprehensive test suite with 12 passing tests
- **Clean Architecture**: Logical separation between indexing, retrieval, API, and CLI layers

## Installation

### From PyPI

```bash
pip install athenaeum

# With deployment extras for AWS CDK
pip install athenaeum[deploy]
```

### From Source

This project uses [uv](https://github.com/astral-sh/uv) for package management and Python 3.12+.

```bash
# Clone the repository
git clone https://github.com/matthewhanson/athenaeum.git
cd athenaeum

# Install dependencies (uv will automatically create/use .venv)
uv sync

# Or install in development mode
uv pip install -e ".[dev]"
```

## Usage

### CLI Commands

All commands are available via the `athenaeum` CLI:

```bash
# Show version
uv run athenaeum --version

# Get help
uv run athenaeum --help
```

#### Build an Index

```bash
# Basic indexing (defaults to *.md files)
uv run athenaeum index ./your_markdown_docs --output ./index

# Custom embedding model and chunk settings
uv run athenaeum index ./docs \
  --output ./index \
  --embed-model "sentence-transformers/all-MiniLM-L6-v2" \
  --chunk-size 1024 \
  --chunk-overlap 200

# Exclude specific patterns
uv run athenaeum index ./docs \
  --output ./index \
  --exclude "**/.git/**" "**/__pycache__/**"
```

#### Query the Index

```bash
# Basic query
uv run athenaeum query "What is the main topic?" --output ./index

# With more context
uv run athenaeum query "Explain the key concepts" \
  --output ./index \
  --top-k 10 \
  --sources
```

#### Run the MCP Server

```bash
# Start server with default settings
uv run athenaeum serve --index ./index

# Custom host and port
uv run athenaeum serve --index ./index --host 0.0.0.0 --port 8000

# With auto-reload for development
uv run athenaeum serve --index ./index --reload
```

## AWS Lambda Deployment

Athenaeum provides example deployment configurations for AWS Lambda using **Docker container images** (required for PyTorch + ML dependencies).

### Two Deployment Approaches

#### 1. **Application-Specific Deployment** (Recommended)

Your application has its own Dockerfile that:

- Installs `athenaeum` as a dependency (from PyPI)
- Copies your application-specific index into the container image
- Configures application-specific settings

**This is the recommended approach.** See `examples/deployment/README.md` for:

- Complete Dockerfile template
- Step-by-step customization guide
- CDK deployment example
- Production best practices

**Benefits:**

- Index baked into Docker image (no S3 download latency)
- Simpler architecture (no S3 bucket needed)
- Faster cold starts
- Easier to version and deploy

#### 2. **Example Template Deployment**

Athenaeum includes complete example deployment files in `examples/deployment/`:

- `Dockerfile` - Reference implementation
- `requirements.txt` - Lambda dependencies
- `run.sh` - Lambda Web Adapter startup script
- `.dockerignore` - Build optimization

**Use the template**:

```bash
# Copy the template to your project
cp -r athenaeum/examples/deployment/* my-project/

# Customize for your needs:
# - Add your index: COPY index/ /var/task/index
# - Update requirements if needed
# - Modify environment variables
```

### Quick Start with CDK

```python
from aws_cdk import Stack, CfnOutput, Duration
from athenaeum.infra import MCPServerContainerConstruct
import os

class MyStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        server = MCPServerContainerConstruct(
            self, "Server",
            dockerfile_path="./Dockerfile",      # Your Dockerfile
            docker_build_context=".",             # Build from current dir
            index_path=None,                      # Index baked into image
            environment={
                "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
            },
            memory_size=2048,  # 2GB for ML workloads
            timeout=Duration.minutes(5),
        )

        CfnOutput(self, "ApiUrl", value=server.api_url)
```

**Deploy:**

```bash
export OPENAI_API_KEY=sk-...
cdk deploy
```

### Deployment Architecture

**Container Image Approach:**

- Lambda function with Docker container (up to 10GB)
- Index baked into image at `/var/task/index`
- FastAPI + Lambda Web Adapter for HTTP handling
- API Gateway REST API with CORS
- CloudWatch Logs for monitoring

**Resource Limits:**

- Docker image: 10GB uncompressed, 10GB compressed in ECR
- Lambda memory: 128MB - 10GB (recommend 2GB for ML)
- Lambda storage: /tmp up to 10GB (ephemeral)
- Timeout: Up to 15 minutes (recommend 5 minutes)

**Cost Estimate:** ~$1-2/month for 10K requests with 2GB memory and 10MB index

**Complete guides:**

- [`examples/deployment/README.md`](examples/deployment/README.md) - Deployment template and instructions
- [`examples/README.md`](examples/README.md) - Examples overview

## MCP Server API

The server provides clean HTTP endpoints (no `/v1` prefix) for RAG operations:

### Endpoints

#### `GET /`

Landing page with API documentation

**Response:**

```json
{
  "service": "Athenaeum MCP Server",
  "version": "1.0",
  "endpoints": {
    "/health": "Health check",
    "/models": "List available models",
    "/search": "Search for context chunks",
    "/chat": "Chat with RAG"
  }
}
```

#### `GET /health`

Health check endpoint

**Response:**

```json
{"status": "healthy"}
```

#### `GET /models`

List available retrieval models

**Response:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "athenaeum-index-retrieval",
      "object": "model",
      "created": 1234567890,
      "owned_by": "athenaeum"
    }
  ]
}
```

#### `POST /search`

Search for context chunks matching a query

**Request:**

```json
{
  "query": "What are the key concepts?",
  "limit": 5
}
```

**Response:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "doc1.txt",
      "content": "Context chunk content...",
      "metadata": {
        "path": "doc1.txt",
        "score": 0.95
      }
    }
  ],
  "model": "athenaeum-index-retrieval"
}
```

#### `POST /chat`

Generate an answer using RAG

**Request:**

```json
{
  "messages": [
    {"role": "user", "content": "What are the main topics?"}
  ],
  "model": "athenaeum-index-retrieval"
}
```

**Response:**

```json
{
  "id": "chat-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "athenaeum-index-retrieval",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The main topics are..."
      },
      "finish_reason": "stop"
    }
  ]
}
```


## Model Context Protocol (MCP)

In addition to the REST API, Athenaeum supports the **Model Context Protocol** for integration with AI tools like GitHub Copilot and Claude Desktop.

### MCP Endpoint

The server exposes an SSE endpoint at `/mcp` that implements the MCP protocol:

```bash
# Local development
http://localhost:8000/mcp

# AWS deployment  
https://your-api.execute-api.region.amazonaws.com/prod/mcp
```

### MCP Tools

- **`search`**: Search indexed documents for relevant passages
  - Parameters: `query` (string), `limit` (int, default 10)
  - Returns: Array of search results with content and metadata

- **`chat`**: Ask questions with RAG-powered answers
  - Parameters: `query` (string), `max_tokens` (int, default 1024)
  - Returns: Generated answer with source citations

### MCP Resources

- **`index://status`**: Get index status (file sizes, health check)

### Using with GitHub Copilot

1. Configure your GitHub connector to point to `/mcp`:
   ```
   https://your-deployment-url.com/mcp
   ```

2. GitHub will connect via SSE and discover available tools

3. Use the tools in your Copilot chat:
   - "Search the docs for information about X"
   - "What does the documentation say about Y?"

See [`MCP_PROTOCOL.md`](MCP_PROTOCOL.md) for complete documentation including:
- Testing with MCP Inspector
- AWS Lambda considerations for SSE streaming
- Environment variables
- Troubleshooting

## Project Structure

The codebase is organized by concern with clear separation between indexing, retrieval, and interface layers:

```text
src/athenaeum/
├── utils.py              # Shared utilities (~22 lines)
│   └── setup_settings() - Configure LlamaIndex with MarkdownNodeParser
│
├── indexer.py            # Markdown indexing (~169 lines)
│   ├── build_index() - PUBLIC API - Build FAISS index from markdown
│   └── _validate_paths(), _build_document_reader(), etc. - Private helpers
│
├── retriever.py          # Query & retrieval (~109 lines)
│   ├── query_index() - PUBLIC API - Query with answer generation
│   ├── retrieve_context() - PUBLIC API - Retrieve context chunks
│   └── _load_index_storage() - Private helper
│
├── mcp_server.py         # FastAPI MCP server (~160 lines)
│   ├── GET /            - Landing page with API docs
│   ├── GET /health      - Health check
│   ├── GET /models      - List models
│   ├── POST /search     - Search for context
│   └── POST /chat       - Chat with RAG
│
└── main_cli.py           # Typer CLI (~160 lines)
    ├── index            - Build markdown index
    ├── query            - Query index
    └── serve            - Launch MCP server

tests/
├── test_utils.py         # Test shared utilities
├── test_indexer.py       # Test indexing functions
├── test_retriever.py     # Test retrieval functions
├── test_mcp_server.py    # Test all API endpoints
└── test_cli.py           # Test CLI commands
```

### Design Principles

1. **Markdown-First**: Uses LlamaIndex's `MarkdownNodeParser` for structure-aware chunking
2. **Separation of Concerns**: Indexing (`indexer.py`) vs Retrieval (`retriever.py`)
3. **Minimal Public API**: Internal helpers prefixed with `_`
4. **Thin Interface Layers**: CLI and API delegate to business logic
5. **No Duplication**: Only truly shared code in `utils.py`

## Key Dependencies

- **LlamaIndex**: Vector search, `MarkdownNodeParser`, and RAG orchestration
- **FastAPI**: HTTP API server
- **FAISS**: Efficient vector storage and similarity search
- **HuggingFace Transformers**: Local embeddings (all-MiniLM-L6-v2)
- **Typer**: CLI framework
- **Pydantic**: Data validation for API

### Deployment Dependencies (optional)

- **AWS CDK**: Infrastructure as code for Lambda deployment
- **Lambda Web Adapter**: AWS's official adapter for running web apps on Lambda
- **python-jose**: JWT/OAuth token validation

## Environment Variables

```bash
# Optional: Override default LLM for answer generation
export OPENAI_MODEL="gpt-4o-mini"

# For MCP server (set automatically by CLI)
export ATHENAEUM_INDEX_DIR="/path/to/index"
```

## Markdown Indexing

Athenaeum uses LlamaIndex's `MarkdownNodeParser` for structure-aware chunking that respects:

- Heading hierarchy
- Code blocks
- Tables
- Blockquotes

**Default chunk settings:**

- Size: 1024 characters (~200 words)
- Overlap: 200 characters

See [MARKDOWN_INDEXING_BEST_PRACTICES.md](MARKDOWN_INDEXING_BEST_PRACTICES.md) for detailed guidance on optimizing markdown documents for RAG.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup and workflow
- Running tests and code quality checks
- Code style guidelines
- Pull request process

## License

MIT
