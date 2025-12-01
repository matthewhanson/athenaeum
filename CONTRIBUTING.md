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

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=athenaeum --cov-report=term-missing
```

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
ruff check .           # Lint
ruff format .          # Format
mypy src/athenaeum     # Type check
bandit -r src/athenaeum  # Security scan
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
```
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

```
athenaeum/
├── src/athenaeum/         # Main package
│   ├── infra/             # CDK constructs
│   ├── indexer/           # Indexing logic
│   ├── retriever/         # Retrieval logic
│   ├── mcp_server/        # MCP server implementation
│   └── main_cli.py        # CLI entry point
├── tests/                 # Test suite
├── examples/              # Example CDK applications
└── docs/                  # Additional documentation
```

## Documentation

- Update README.md for user-facing changes
- Update DEPLOYMENT.md for infrastructure changes
- Add docstrings to new functions and classes
- Update CHANGELOG.md with notable changes

## AWS/CDK Development

When working on CDK constructs:

1. Test locally before deploying:
   ```bash
   cd examples
   cdk synth
   ```

2. Use `--hotswap` for fast code-only deploys:
   ```bash
   cdk deploy --hotswap
   ```

3. Follow L3 construct patterns (see `src/athenaeum/infra/`)

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
