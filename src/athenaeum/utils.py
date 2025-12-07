"""
Shared utilities used across indexing and retrieval.
"""

from __future__ import annotations

import os

from llama_index.core import Settings
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


def setup_settings(
    chunk_size: int = 1024,
    chunk_overlap: int = 200,
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    llm_provider: str | None = None,
    llm_model: str | None = None,
):
    """
    Configure LlamaIndex settings for markdown-aware embedding and text splitting.

    Uses sentence-transformers for embeddings (local, consistent).
    LLM can be OpenAI, AWS Bedrock, or others (optional - only needed for chat/generation).

    Args:
        chunk_size: Size of text chunks for splitting
        chunk_overlap: Overlap between chunks
        embed_model: HuggingFace embedding model (default: sentence-transformers/all-MiniLM-L6-v2)
        llm_provider: LLM provider - "openai", "bedrock", etc. (default: None, only needed for chat)
        llm_model: Model name for the LLM provider
    """
    # Embeddings: Always use sentence-transformers for consistency
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model)

    # LLM: Support multiple providers (optional, only needed for chat/generation)
    if llm_provider == "openai":
        from llama_index.llms.openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable must be set for OpenAI provider")
        Settings.llm = OpenAI(
            model=llm_model or "gpt-4o-mini",
            api_key=api_key,
        )
    elif llm_provider == "bedrock":
        from llama_index.llms.bedrock import Bedrock

        Settings.llm = Bedrock(model=llm_model or "anthropic.claude-v2")
    elif llm_provider is not None:
        raise ValueError(f"Unsupported LLM provider: {llm_provider}")
    # If llm_provider is None, don't configure an LLM (search-only mode)

    Settings.node_parser = MarkdownNodeParser(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
