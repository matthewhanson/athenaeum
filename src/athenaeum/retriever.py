"""
Query and retrieval functions for the FAISS-backed index.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from llama_index.core import StorageContext, load_index_from_storage
from llama_index.vector_stores.faiss import FaissVectorStore

from athenaeum.utils import setup_settings


def _load_index_storage(index_dir: Path) -> StorageContext:
    """Load FAISS vector store and storage context from disk."""
    if not index_dir.exists():
        raise FileNotFoundError(
            f"Index directory not found: {index_dir}\n"
            f"Build an index first with: athenaeum index <source_dir> --output {index_dir}"
        )

    faiss_path = index_dir / "faiss.index"
    if not faiss_path.exists():
        raise FileNotFoundError(
            f"FAISS index file not found: {faiss_path}\n"
            f"The directory exists but doesn't contain a valid index.\n"
            f"Build an index first with: athenaeum index <source_dir> --output {index_dir}"
        )

    vector_store = FaissVectorStore.from_persist_path(str(faiss_path))
    return StorageContext.from_defaults(
        persist_dir=str(index_dir),
        vector_store=vector_store,
    )


def query_index(
    index_dir: Path,
    question: str,
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    top_k: int = 5,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """
    Query an existing index with a question and generate an answer.

    Uses sentence-transformers for embeddings (must match indexing model).
    LLM provider can be OpenAI, AWS Bedrock, or others.

    Args:
        index_dir: Path to the index directory
        question: The query to search for
        embed_model: HuggingFace embedding model (default: sentence-transformers/all-MiniLM-L6-v2)
        llm_provider: LLM provider - "openai", "bedrock", etc. (default: "openai")
        llm_model: Model name for the LLM provider (default: gpt-4o-mini for OpenAI)
        top_k: Number of results to return
        system_prompt: Optional system prompt to guide the LLM's behavior

    Returns:
        Dict with 'answer' and 'sources' keys
    """
    from llama_index.core.prompts import PromptTemplate
    
    setup_settings(embed_model=embed_model, llm_provider=llm_provider, llm_model=llm_model)
    storage_context = _load_index_storage(index_dir)
    index = load_index_from_storage(storage_context)

    # Create query engine with optional system prompt
    query_engine_kwargs = {"similarity_top_k": top_k}
    if system_prompt:
        # Create a custom template that includes the system prompt
        qa_template = PromptTemplate(
            f"{system_prompt}\n\n"
            "Context information is below.\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n"
            "Given the context information and not prior knowledge, "
            "answer the query.\n"
            "Query: {query_str}\n"
            "Answer: "
        )
        query_engine_kwargs["text_qa_template"] = qa_template
    
    qe = index.as_query_engine(**query_engine_kwargs)
    resp = qe.query(question)

    # Extract sources
    sources = []
    if hasattr(resp, "source_nodes") and resp.source_nodes:
        for n in resp.source_nodes:
            node = getattr(n, "node", n)
            sources.append(
                {
                    "path": (node.metadata or {}).get("source_path", "unknown"),
                    "score": getattr(n, "score", None),
                }
            )

    return {"answer": str(resp), "sources": sources}


def retrieve_context(
    index_dir: Path,
    question: str,
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Retrieve context chunks for a query without generating an answer.

    Uses sentence-transformers for embeddings (must match indexing model).

    Args:
        index_dir: Path to the index directory
        question: The query to search for
        embed_model: HuggingFace embedding model (default: sentence-transformers/all-MiniLM-L6-v2)
        top_k: Number of results to return

    Returns:
        List of dicts with 'content' and 'metadata' keys
    """
    setup_settings(embed_model=embed_model)
    storage_context = _load_index_storage(index_dir)
    index = load_index_from_storage(storage_context)

    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(question)

    # Extract context and metadata
    contexts = []
    for node in nodes:
        contexts.append(
            {
                "content": node.get_content(),
                "metadata": {
                    "path": (node.metadata or {}).get("source_path", "unknown"),
                    "score": getattr(node, "score", None),
                },
            }
        )

    return contexts


def retrieve_timeline(
    index_dir: Path,
    start_year: int | None = None,
    end_year: int | None = None,
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Retrieve timeline entries within a year range.
    
    This performs numerical filtering on timeline entries by extracting years
    from breadcrumb annotations like "[Third Era Timeline > Year 6050]".
    
    Unlike semantic search, this finds all entries where the year number falls
    within the specified range, making it ideal for queries like:
    - "What happened between 6000 and 6500?"
    - "Events after year 6000"
    - "Timeline before year 1000"
    
    Args:
        index_dir: Path to the index directory
        start_year: Starting year (inclusive), None means no lower bound
        end_year: Ending year (inclusive), None means no upper bound
        embed_model: HuggingFace embedding model (must match indexing model)
        top_k: Maximum number of results to return (after filtering)
        
    Returns:
        List of dicts with 'content', 'metadata', and 'year' keys, sorted by year
        
    Example:
        # Find events between years 6000-6500
        results = retrieve_timeline(
            index_dir=Path("index"),
            start_year=6000,
            end_year=6500,
            top_k=20
        )
    """
    setup_settings(embed_model=embed_model)
    storage_context = _load_index_storage(index_dir)
    index = load_index_from_storage(storage_context)
    
    # Get all nodes from the docstore
    all_nodes = list(index.docstore.docs.values())
    
    # Pattern to extract year from breadcrumb: [... > Year 6050] or [... > Date 6050-3-14]
    year_pattern = re.compile(r'\[.*?(?:Year|Date|Years|circa Year)\s+(\d+)', re.IGNORECASE)
    
    matching_entries = []
    for node in all_nodes:
        text = node.get_content()
        
        # Look for year in breadcrumb
        match = year_pattern.search(text)
        if match:
            year = int(match.group(1))
            
            # Check if year is in range
            if start_year is not None and year < start_year:
                continue
            if end_year is not None and year > end_year:
                continue
            
            # This entry matches the range
            matching_entries.append({
                "content": text,
                "metadata": {
                    "path": (node.metadata or {}).get("source_path", "unknown"),
                    "year": year,
                },
                "year": year,
            })
    
    # Sort by year (ascending)
    matching_entries.sort(key=lambda x: x["year"])
    
    # Limit results
    return matching_entries[:top_k]
