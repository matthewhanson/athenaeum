"""
Shared utilities used across indexing and retrieval.
"""

from __future__ import annotations

import os

from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


def setup_settings(embed_model: str, chunk_size: int = 1024, chunk_overlap: int = 200):
    """Configure LlamaIndex settings for markdown-aware embedding and text splitting."""
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model)
    Settings.llm = OpenAI(model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    Settings.node_parser = MarkdownNodeParser(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
