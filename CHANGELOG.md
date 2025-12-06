# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Deployment architecture: Container images with baked-in index (recommended over S3 download)
- Documentation restructure: Removed duplicative DEPLOYMENT.md, consolidated into examples/deployment/README.md
- Simplified deployment approach: Application-specific Dockerfiles instead of shared templates

### Added
- Comprehensive deployment template in examples/deployment/
- Reference implementation: Nomikos project demonstrating production deployment

## [0.1.0] - 2025-01-XX

### Added
- Initial release of Athenaeum RAG system
- Markdown-focused document indexing with LlamaIndex and MarkdownNodeParser
- FAISS vector search with HuggingFace embeddings (BAAI/bge-small-en-v1.5)
- FastAPI-based MCP (Model Context Protocol) server
- CLI tools for indexing, querying, and serving
- Support for OpenAI LLM providers
- AWS Lambda deployment support via CDK with Docker container images
- Reusable L3 CDK construct:
  - `MCPServerContainerConstruct`: Complete MCP server deployment with container images
- Comprehensive documentation and examples
- Hypermodern Python tooling:
  - ruff for linting and formatting
  - mypy for type checking
  - bandit for security scanning
  - pre-commit hooks
  - pytest for testing

### Features
- **Indexing**: Recursive markdown file discovery with structure-aware chunking
- **Retrieval**: Vector similarity search with configurable top-k
- **Chat**: Conversational interface with RAG context
- **MCP Server**: RESTful API with `/search` and `/chat` endpoints
- **Deployment**: Container-based Lambda deployment supporting PyTorch + full ML stack
- **Optimization**: PyTorch CPU-only builds (~2GB container vs ~10GB with CUDA)

### Documentation
- Comprehensive README with installation, usage, and deployment overview
- Deployment template guide in examples/deployment/README.md
- Example overview in examples/README.md
- Inline code documentation and type hints

[Unreleased]: https://github.com/matthewhanson/athenaeum/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/matthewhanson/athenaeum/releases/tag/v0.1.0
