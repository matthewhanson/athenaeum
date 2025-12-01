# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-01-XX

### Added
- Initial release of Athenaeum RAG system
- Markdown-focused document indexing with LlamaIndex
- FAISS vector search with HuggingFace embeddings (BAAI/bge-small-en-v1.5)
- FastAPI-based MCP (Model Context Protocol) server
- OAuth2 authentication support for AWS Cognito
- CLI tools for indexing, querying, and chatting
- Support for both OpenAI and Ollama LLM providers
- AWS Lambda deployment support via CDK
- Reusable L3 CDK constructs:
  - `DependenciesLayerConstruct`: Optimized Lambda layer with PyTorch CPU-only
  - `MCPServerConstruct`: Complete MCP server deployment
- Dual-mode construct support for local development and published packages
- Comprehensive documentation (README, DEPLOYMENT guide)
- Hypermodern Python tooling:
  - ruff for linting and formatting
  - mypy for type checking
  - bandit for security scanning
  - pre-commit hooks
  - pytest for testing

### Features
- **Indexing**: Recursive markdown file discovery and indexing
- **Retrieval**: Vector similarity search with configurable top-k
- **Chat**: Multi-turn conversational interface with context
- **MCP Server**: RESTful API with `/query` and `/chat` endpoints
- **Authentication**: OAuth2 bearer token validation
- **Deployment**: One-command CDK deployment to AWS Lambda
- **Optimization**: PyTorch CPU-only builds (~1.2GB vs 47GB with CUDA)

### Documentation
- Comprehensive README with installation and usage examples
- DEPLOYMENT guide with CDK setup and --hotswap explanation
- Example CDK application in `examples/` directory
- Inline code documentation and type hints

[Unreleased]: https://github.com/matthewhanson/athenaeum/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/matthewhanson/athenaeum/releases/tag/v0.1.0
