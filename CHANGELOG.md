# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-12-25

Initial release of Athenaeum - A specialized RAG (Retrieval-Augmented Generation) system designed for RPG world knowledge bases.

### Features
- **🎲 RPG-Optimized:**
  - Timeline search tool for chronological queries with year-based filtering
  - Classification system for secret knowledge management (PUBLIC/GUARDED/FORBIDDEN)
  - Multi-persona support (switch AI characters per request)
  - Markdown-first indexing with structure-aware parsing
  - Semantic search for finding relevant lore
  - Tool-calling chat with autonomous multi-search

- **🛠️ Developer-Friendly:**
  - FastAPI server with clean REST API
  - AWS Lambda deployment with CDK constructs
  - Comprehensive test suite
  - Clean architecture with separated concerns
  - Reusable L3 CDK constructs

- **📚 Documentation:**
  - Complete API reference (API.md)
  - Quick Start guide for RPG projects
  - Live example: Nomikos (Shadow World knowledge base)
  - Comprehensive README with use cases

[Unreleased]: https://github.com/matthewhanson/athenaeum/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/matthewhanson/athenaeum/releases/tag/v0.1.0
