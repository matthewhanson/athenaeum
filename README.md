# Athenaeum

*Give your LLM a library.*

A RAG (Retrieval-Augmented Generation) system built with LlamaIndex and FastAPI that provides an MCP-compatible server for document retrieval and question answering.

## Features

- **Vector Search**: FAISS-backed vector search using HuggingFace embeddings
- **PDF Preprocessing**: Convert PDFs to Markdown with multiple engines (unstructured, pymupdf, docling)
- **MCP Server**: HTTP API with clean endpoints for retrieval and chat
- **CLI Tools**: Convert PDFs, build indices, query, and run the server
- **Well-Tested**: Comprehensive test suite with 12 passing tests
- **Clean Architecture**: Logical separation between indexing, retrieval, API, and CLI layers

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for package management and Python 3.12.

```bash
# Clone the repository
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

#### Convert PDFs to Markdown

```bash
# Using hybrid engine (RECOMMENDED for complex PDFs like game books)
# Combines unstructured (headings) + docling (tables)
uv run athenaeum convert ./pdfs --out ./markdown_output --engine hybrid

# Using default engine (unstructured only)
uv run athenaeum convert ./pdfs --out ./markdown_output --engine unstructured

# Using PyMuPDF (faster, simpler)
uv run athenaeum convert ./pdfs --out ./markdown_output --engine pymupdf

# Using Docling (better tables)
uv run athenaeum convert ./pdfs --out ./markdown_output --engine docling

# Overwrite existing files
uv run athenaeum convert ./pdfs --out ./markdown_output --overwrite

# Extract images from PDFs
uv run athenaeum convert ./pdfs --out ./markdown_output --images
```

**For complex PDFs with images and tables:** Use `--engine hybrid` for best results. The hybrid engine combines unstructured (for headings) with docling (for tables), providing the most accurate conversion for complex documents.

#### Build an Index

```bash
# Basic indexing
uv run athenaeum index ./your_documents --output ./index

# With custom patterns
uv run athenaeum index ./docs \
  --output ./index \
  --include "*.md" "*.txt" \
  --exclude "**/.git/**" "**/__pycache__/**"

# Custom embedding model and chunk settings
uv run athenaeum index ./docs \
  --output ./index \
  --embed-model "sentence-transformers/all-MiniLM-L6-v2" \
  --chunk-size 800 \
  --chunk-overlap 120
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
    "/retrieve": "Retrieve context chunks",
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

#### `POST /retrieve`
Retrieve context chunks matching a query

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

## Testing

Run the comprehensive test suite (12 tests):

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_indexer.py -v

# Run with coverage
uv run pytest tests/ --cov=athenaeum --cov-report=html
```

**Test Coverage:**
- ✅ CLI commands (version, index)
- ✅ Utils (setup_settings)
- ✅ Indexer (build_index with various scenarios)
- ✅ Retriever (query_index, retrieve_context)
- ✅ MCP Server (all HTTP endpoints)

## Project Structure

The codebase is organized by concern with clear separation between indexing, retrieval, and interface layers:

```
src/athenaeum/
├── utils.py              # Shared utilities (22 lines)
│   └── setup_settings() - Configure LlamaIndex Settings
│
├── indexer.py            # Indexing & PDF preprocessing (344 lines)
│   ├── PDF Conversion:
│   │   ├── collect_pdfs()
│   │   ├── convert_pdfs_to_markdown()
│   │   └── _convert_with_*() - Engine implementations
│   └── Index Building:
│       ├── build_index() - PUBLIC API
│       └── _validate_paths(), _build_document_reader(), etc. - Private helpers
│
├── retriever.py          # Query & retrieval (109 lines)
│   ├── query_index() - PUBLIC API - Query with answer generation
│   ├── retrieve_context() - PUBLIC API - Retrieve context chunks
│   └── _load_index_storage() - Private helper
│
├── mcp_server.py         # FastAPI MCP server (201 lines)
│   ├── GET /            - Landing page with API docs
│   ├── GET /health      - Health check
│   ├── GET /models      - List models
│   ├── POST /retrieve   - Retrieve context
│   └── POST /chat       - Chat with RAG
│
└── main_cli.py           # Typer CLI (197 lines)
    ├── convert          - PDF to Markdown
    ├── index            - Build index
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

1. **Cohesion**: PDF conversion is in `indexer.py` because it's preprocessing for indexing
2. **Separation of Concerns**: Indexing (`indexer.py`) vs Retrieval (`retriever.py`)
3. **Minimal Public API**: Internal helpers prefixed with `_`
4. **Thin Interface Layers**: CLI and API delegate to business logic
5. **No Duplication**: Only truly shared code in `utils.py`

## Key Dependencies

- **LlamaIndex**: Vector search, document loading, and RAG orchestration
- **FastAPI**: HTTP API server
- **FAISS**: Efficient vector storage and similarity search
- **HuggingFace Transformers**: Local embeddings (all-MiniLM-L6-v2)
- **Typer**: CLI framework
- **Pydantic**: Data validation for API

### PDF Conversion Engines

- **unstructured** (default): Best heading/section fidelity
- **pymupdf**: Fast fallback with pymupdf4llm
- **docling**: Strong structure preservation (optional)

## Environment Variables

```bash
# Optional: Override default LLM for answer generation
export OPENAI_MODEL="gpt-4o-mini"

# For MCP server (set automatically by CLI)
export ATHENAEUM_INDEX_DIR="/path/to/index"
```

## Development

```bash
# Install development dependencies
uv sync --all-extras

# Run tests with coverage
uv run pytest tests/ --cov=athenaeum --cov-report=term-missing

# Format code
uv run black src/ tests/

# Type checking
uv run mypy src/
```

## License

MIT
