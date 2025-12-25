# Athenaeum

[![PyPI - Version](https://img.shields.io/pypi/v/athenaeum)](https://pypi.org/project/athenaeum/)
[![Python Version](https://img.shields.io/pypi/pyversions/athenaeum)](https://pypi.org/project/athenaeum/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*Give your LLM a library card to an RPG world.*

A specialized RAG (Retrieval-Augmented Generation) system designed for **RPG world knowledge bases**. Built with LlamaIndex and FastAPI, Athenaeum excels at indexing and retrieving campaign settings, timelines, lore, and character information—perfect for game masters, players, and world-builders who want AI assistants with deep knowledge of their fantasy worlds.

**Live Example:** [Nomikos](https://nomikos.vroomfogle.com) - A Shadow World knowledge base powered by Athenaeum, featuring the ancient scholar Andraax who can answer questions about Kulthea's history, geography, and lore. Try asking about the Wars of Dominion, Dragonlords, or the College of Loremasters!

## Features

### 🎲 RPG-Optimized
- **⏱️ Timeline Search**: Query events by year ranges ("What happened between SE 1000-2000?")
- **🔒 Secret Knowledge Management**: Optional classification system to guard sensitive campaign information
- **🎭 Multi-Persona Support**: Switch between AI characters (wise scholar, neutral librarian, NPC) per request
- **📜 Markdown-First**: Structure-aware parsing for headings, tables, and nested content
- **🔍 Semantic Search**: Find relevant lore even when exact terms don't match
- **🤖 Tool-Calling Chat**: LLM searches multiple times to build comprehensive answers

### 🛠️ Developer-Friendly
- **⚡ FastAPI Server**: Clean REST API with OpenAPI docs ([API Reference](API.md))
- **🐳 Lambda Ready**: Container-based serverless deployment with AWS CDK
- **🧪 Well-Tested**: Comprehensive test suite covering all functionality
- **🎯 Clean Architecture**: Separation between indexing, retrieval, API, and CLI layers
- **📦 Reusable Constructs**: L3 CDK constructs for easy deployment

## RPG Use Cases

Athenaeum is purpose-built for RPG campaign settings and world-building. Here's what makes it special:

### Campaign Knowledge Base

**Example: [Nomikos (Shadow World)](https://nomikos.vroomfogle.com)**
- **30+ years of campaign lore** indexed from markdown source documents
- **Two AI personas**: Andraax (cryptic ancient scholar who guards secrets) and Scribe (neutral librarian who answers everything)
- **Timeline search**: Query thousands of years of in-game history ("What happened during the Wars of Dominion?")
- **Secret classification**: Forbidden topics (artifact creation methods, summoning rituals) are deflected while public lore flows freely
- **First-person roleplay**: Andraax speaks as a 6000-year-old elf who witnessed the events

### What You Can Build

**Game Master Assistant:**
- Query NPC backgrounds, faction relationships, and plot threads
- Timeline search for historical context ("What was happening 100 years before this campaign?")
- Multiple personas (town guard, sage, suspicious merchant) with different knowledge levels

**Player-Facing Lore Database:**
- Public persona for common knowledge, secret persona for DM-only information
- Classification guards spoilers and surprise plot elements
- Players ask questions in-character and get in-world responses

**World-Building Tool:**
- Vector search finds thematic connections across your lore
- Timeline search reveals patterns in your world's history
- Chat tool-calling lets you explore complex questions across multiple sources

**Campaign Prep:**
- "What factions are active in this region?"
- "Show me all events involving the royal family between years 450-600"
- "What do players know about the artifact?" (uses classification to avoid spoilers)

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

## Quick Start for RPG Projects

Here's how to set up a knowledge base for your RPG campaign:

### 1. Prepare Your Campaign Documents

Organize your lore as markdown files:

```
my-campaign/
├── world/
│   ├── geography.md      # Continents, cities, terrain
│   ├── history.md        # Timeline with year markers
│   └── factions.md       # Organizations and groups
├── characters/
│   ├── npcs.md          # Non-player characters
│   └── player-guide.md  # Public information for players
└── secrets/
    └── dm-only.md       # Plot twists, secret organizations
```

**Timeline formatting** (for chronological queries):

```markdown
## The Great War (Year 1245-1267)
The kingdom fell into civil war...

## Peace Treaty (Year 1268)
King Aldric signed the Treaty of...
```

### 2. Build the Index

```bash
# Install athenaeum
pip install athenaeum

# Index your campaign lore
athenaeum index ./my-campaign --output ./campaign-index

# Start the API server
athenaeum serve --index ./campaign-index --port 8000
```

### 3. Query Your World

```bash
# Semantic search
curl -X POST http://localhost:8000/chat \
  -d '{"messages": [{"role": "user", "content": "Tell me about King Aldric"}]}'

# Timeline query
curl -X POST http://localhost:8000/chat \
  -d '{"messages": [{"role": "user", "content": "What happened between years 1200-1300?"}]}'
```

### 4. Add Personas (Optional)

Create `prompts/sage_system_prompt.md`:

```markdown
You are Eldrin the Sage, keeper of historical records. You speak formally
and refer to events you've witnessed firsthand. When asked about secret
information, deflect: "That knowledge is restricted to the Council..."
```

Then use it:

```bash
curl -X POST http://localhost:8000/chat \
  -d '{"messages": [{"role": "user", "content": "What do you know of the war?"}], "persona": "sage"}'
```

### 5. Deploy to Production (Optional)

See [Deployment](#deployment) section for AWS Lambda setup. Cost: ~$1-2/month for typical campaign use.

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

#### Run the API Server

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
from athenaeum.infra import APIServerContainerConstruct
import os

class MyStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        server = APIServerContainerConstruct(
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

## API Reference

Athenaeum provides a FastAPI-based REST API with multiple endpoints for document retrieval and question answering.

**Quick Overview:**
- **`GET /health`** - Health check
- **`GET /models`** - List available models
- **`GET /personas`** - List available personas
- **`POST /search`** - Raw vector search (returns context chunks)
- **`POST /chat`** - Interactive chat with tool calling (primary endpoint)

**Key Features:**
- 🎭 **Personas**: Switch AI behavior per-request without redeployment
- ⏱️ **Timeline Tool**: LLM autonomously searches by year ranges
- 🔒 **Classification**: Optional pre-RAG filtering for secret knowledge
- 🤖 **Tool Calling**: LLM can search multiple times to build comprehensive answers

**Complete Documentation:** See [API.md](API.md) for detailed endpoint documentation, request/response formats, examples, and configuration.

**Interactive Docs:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Environment Variables

**Core Configuration:**

```bash
# Required for chat/answer endpoints
export OPENAI_API_KEY="sk-..."

# Index location (set automatically by CLI)
export ATHENAEUM_INDEX_DIR="/path/to/index"
```

**Persona Configuration (optional):**

```bash
export CHAT_SYSTEM_PROMPT_DIR="/var/task"  # Directory with persona files
export CHAT_SYSTEM_PROMPT_FILE="/var/task/default_system_prompt.md"  # Default persona
```

See [API.md](API.md#environment-variables) for complete list of environment variables.

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
