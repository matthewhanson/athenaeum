"""
Shared utilities used across indexing and retrieval.
"""

from __future__ import annotations

import os

from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


def setup_settings(embed_model: str, chunk_size: int = 800, chunk_overlap: int = 120):
    """Configure LlamaIndex settings for embedding and text splitting."""
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model)
    Settings.llm = OpenAI(model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    Settings.node_parser = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
