# Contributing to Athenaeum

Thank you for your interest in contributing to Athenaeum! This document provides guidelines and instructions for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git

### Initial Setup

1. Fork and clone the repository:

   ```bash
   git clone https://github.com/matthewhanson/athenaeum.git
   cd athenaeum
   ```

2. Install uv (if not already installed):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Create a virtual environment and install dependencies:

   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev]"
   ```

4. Install pre-commit hooks:

   ```bash
   pre-commit install
   ```

## Development Workflow

### Running Tests

Run the comprehensive test suite:

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_indexer.py -v

# Run with coverage report
uv run pytest tests/ --cov=athenaeum --cov-report=term-missing

# Run with HTML coverage report
uv run pytest tests/ --cov=athenaeum --cov-report=html
```

**Current test coverage:**

- CLI commands (version, index)
- Utils (setup_settings)
- Indexer (build_index with various scenarios)
- Retriever (query_index, retrieve_context)
- MCP Server (all HTTP endpoints)

**Aim for >80% coverage on new code.**

### Code Quality

This project uses several tools to maintain code quality:

- **ruff**: Linting and formatting
- **mypy**: Type checking
- **bandit**: Security scanning
- **pre-commit**: Automated checks before commits

Run all checks manually:

```bash
pre-commit run --all-files
```

Run individual tools:

```bash
uv run ruff check .           # Lint
uv run ruff format .          # Format
uv run mypy src/athenaeum     # Type check
uv run bandit -r src/athenaeum  # Security scan
```

### Pre-commit Hooks

Pre-commit hooks will automatically run on every commit. They will:

- Format code with ruff
- Check for common issues (trailing whitespace, YAML syntax, etc.)
- Validate type hints with mypy
- Scan for security issues with bandit
- Check markdown formatting
- Run spell checking

If hooks fail, fix the issues and commit again.

## Making Changes

### Branching Strategy

- `main`: Stable release branch
- Feature branches: `feature/your-feature-name`
- Bug fixes: `fix/bug-description`

### Commit Messages

Follow conventional commits format:

```text
type(scope): brief description

Detailed explanation if needed.

Fixes #issue-number
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:

- `feat(indexer): add support for PDF files`
- `fix(mcp): handle authentication errors correctly`
- `docs(readme): update installation instructions`

### Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear, atomic commits
3. Add tests for new functionality
4. Update documentation as needed
5. Ensure all tests and checks pass
6. Push your branch and create a pull request
7. Describe your changes clearly in the PR description
8. Link related issues

### Code Style

- Follow PEP 8 guidelines (enforced by ruff)
- Maximum line length: 100 characters
- Use type hints where possible
- Write docstrings for public functions and classes
- Keep functions focused and single-purpose

Example:

```python
def index_documents(
    source_dir: str,
    index_path: str,
    embedding_model: str = "BAAI/bge-small-en-v1.5",
) -> None:
    """Index markdown documents from a directory.

    Args:
        source_dir: Path to directory containing markdown files
        index_path: Path where index will be saved
        embedding_model: HuggingFace model for embeddings

    Raises:
        ValueError: If source_dir doesn't exist
    """
    ...
```

### Testing Guidelines

- Write tests for all new features
- Aim for high test coverage (>80%)
- Use descriptive test names: `test_index_creates_faiss_store`
- Test edge cases and error conditions
- Use fixtures for common test setup

## Project Structure

```text
athenaeum/
├── src/athenaeum/         # Main package
│   ├── infra/             # CDK constructs (MCPServerContainerConstruct)
│   ├── indexer.py         # Indexing logic
│   ├── retriever.py       # Retrieval logic
│   ├── mcp_server.py      # FastAPI MCP server
│   ├── main_cli.py        # CLI entry point
│   └── utils.py           # Shared utilities
├── tests/                 # Test suite
│   ├── test_indexer.py
│   ├── test_retriever.py
│   ├── test_mcp_server.py
│   └── test_cli.py
├── examples/              # Deployment templates and examples
│   └── deployment/        # Lambda container deployment template
└── docs/                  # Additional documentation (if needed)
```

## Documentation

- Update README.md for user-facing changes
- Update examples/deployment/README.md for deployment changes
- Add docstrings to new functions and classes
- Update CHANGELOG.md with notable changes
- Keep documentation minimal and well-organized

## AWS/CDK Development

When working on CDK constructs:

1. Test CDK synthesis locally:

   ```bash
   cd examples
   cdk synth
   ```

2. Test with a real deployment in a separate project (like nomikos)

3. Follow L3 construct patterns (see `src/athenaeum/infra/`)

4. Document construct parameters clearly in docstrings

## Release Process

(Maintainers only)

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` with release date
3. Create release commit: `chore: release v0.2.0`
4. Tag release: `git tag v0.2.0`
5. Push: `git push origin main --tags`
6. Build and publish to PyPI:

   ```bash
   python -m build
   twine upload dist/*
   ```

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
├── api_server.py         # FastAPI REST API server (~540 lines)
│   ├── GET /            - Landing page with API docs
│   ├── GET /health      - Health check
│   ├── GET /models      - List models
│   ├── GET /personas    - List available personas
│   ├── POST /search     - Search for context (raw vector search)
│   ├── POST /answer     - Single-search RAG (quick answers)
│   └── POST /chat       - Multi-search with tool calling (interactive)
│
└── main_cli.py           # Typer CLI (~160 lines)
    ├── index            - Build markdown index
    ├── query            - Query index
    └── serve            - Launch API server

tests/
├── test_utils.py         # Test shared utilities
├── test_indexer.py       # Test indexing functions
├── test_retriever.py     # Test retrieval functions
├── test_api_server.py    # Test all API endpoints
└── test_cli.py           # Test CLI commands
```

## Design Principles

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

## Getting Help

- Open an issue for bug reports or feature requests
- Join discussions in GitHub Discussions
- Check existing issues before creating new ones

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow GitHub's community guidelines

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
