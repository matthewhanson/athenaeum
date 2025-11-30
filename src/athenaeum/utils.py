"""
Shared utilities used across indexing and retrieval.
"""

from __future__ import annotations

import os

from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.llms.ollama import Ollama
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


def setup_settings(
    embed_model: str,
    chunk_size: int = 1024,
    chunk_overlap: int = 200,
    llm_provider: str = "ollama",
    llm_model: str = "llama3.1:8b",
):
    """
    Configure LlamaIndex settings for markdown-aware embedding and text splitting.
    
    Args:
        embed_model: HuggingFace embedding model name
        chunk_size: Size of text chunks for splitting
        chunk_overlap: Overlap between chunks
        llm_provider: LLM provider - "ollama" (local) or "openai" (cloud)
        llm_model: Model name for the provider
    """
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model)
    Settings.node_parser = MarkdownNodeParser(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    
    # Configure LLM based on provider
    if llm_provider == "ollama":
        Settings.llm = Ollama(
            model=llm_model,
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            request_timeout=120.0,
        )
    elif llm_provider == "openai":
        Settings.llm = OpenAI(
            model=llm_model,
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
    else:
        raise ValueError(f"Unknown LLM provider: {llm_provider}. Use 'ollama' or 'openai'.")
