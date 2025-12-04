"""
Business logic for building FAISS-backed vector indexes using LlamaIndex.
Optimized for markdown documents with structure-aware parsing.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pathlib import Path
from fnmatch import fnmatch

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.faiss import FaissVectorStore
import faiss

from athenaeum.utils import setup_settings


# ============================================================================
# Index Building
# ============================================================================

def _validate_paths(inputs: List[Path]) -> List[Path]:
    """Validate that input paths exist."""
    paths = [p for p in inputs if p.exists()]
    if not paths:
        raise FileNotFoundError("No valid input paths found.")
    return paths


def _build_document_reader(
    input_paths: list[Path],
    glob_include: list[str] | None,
    glob_exclude: list[str] | None,
    recursive: bool,
    max_files: Optional[int],
) -> SimpleDirectoryReader:
    """Build a SimpleDirectoryReader that respects include/exclude globs."""
    # Flatten directories and files into a list of paths
    paths: list[str] = []
    for p in input_paths:
        if p.is_dir():
            if recursive:
                paths.extend(str(f) for f in p.rglob("*") if f.is_file())
            else:
                paths.extend(str(f) for f in p.glob("*") if f.is_file())
        else:
            paths.append(str(p))

    # Apply inclusion/exclusion globs
    include_patterns = glob_include or ["**/*"]
    exclude_patterns = glob_exclude or []

    filtered_paths = []
    for path in paths:
        if any(fnmatch(path, ex) for ex in exclude_patterns):
            continue
        if any(fnmatch(path, inc) for inc in include_patterns):
            filtered_paths.append(path)

    if max_files:
        filtered_paths = filtered_paths[:max_files]

    return SimpleDirectoryReader(
        input_files=filtered_paths,
        file_metadata=lambda p: {"source_path": p},
        exclude_hidden=True,
    )


def _create_faiss_storage(index_dir: Path) -> StorageContext:
    """Create or load a FAISS vector store."""
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss_path = index_dir / "faiss.index"

    if faiss_path.exists():
        vector_store = FaissVectorStore.from_persist_path(str(faiss_path))
    else:
        # Create a new FAISS index (384 dims for all-MiniLM-L6-v2)
        faiss_index = faiss.IndexFlatL2(384)
        vector_store = FaissVectorStore(faiss_index=faiss_index)

    return StorageContext.from_defaults(vector_store=vector_store)


def _persist_index(storage_context: StorageContext, index_dir: Path) -> None:
    """Persist the storage context to disk."""
    index_dir.mkdir(parents=True, exist_ok=True)
    storage_context.vector_store.persist(persist_path=str(index_dir / "faiss.index"))
    storage_context.persist(persist_dir=str(index_dir))


def _generate_stats(docs, index: VectorStoreIndex) -> dict:
    """Generate statistics about the indexed documents."""
    num_docs = len(docs)
    nodes_indexed = None
    try:
        nodes_indexed = sum(len(d.nodes) for d in index.docstore.docs.values())
    except Exception:
        pass
    return {
        "documents_ingested": num_docs,
        "index_summary": {"vector_store": "faiss", "nodes_indexed": nodes_indexed},
    }


def build_index(
    inputs: List[Path],
    index_dir: Path,
    chunk_size: int = 1024,
    chunk_overlap: int = 200,
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    recursive: bool = True,
    max_files: Optional[int] = None,
    return_stats: bool = True,
) -> Dict[str, Any] | None:
    """
    Build/update a FAISS-backed index from markdown files.
    
    Uses MarkdownNodeParser for structure-aware chunking that respects
    headings, code blocks, and other markdown elements.
    
    Uses sentence-transformers for embeddings (local, consistent).
    LLM provider is configurable but only used during indexing for metadata.
    
    Args:
        inputs: List of markdown file paths or directories to index
        index_dir: Directory to store the index
        chunk_size: Size of text chunks (default: 1024 for markdown)
        chunk_overlap: Overlap between chunks (default: 200 for markdown)
        embed_model: HuggingFace embedding model (default: sentence-transformers/all-MiniLM-L6-v2)
        llm_provider: LLM provider - "openai", "bedrock", etc. (default: "openai")
        llm_model: Model name for the LLM provider (default: gpt-4o-mini for OpenAI)
        include: Glob patterns to include (defaults to markdown files)
        exclude: Glob patterns to exclude
        recursive: Whether to search directories recursively
        max_files: Maximum number of files to index
        return_stats: Whether to return statistics
        
    Returns:
        Stats dict if return_stats=True, else None
    """
    paths = _validate_paths(inputs)
    setup_settings(chunk_size=chunk_size, chunk_overlap=chunk_overlap, embed_model=embed_model, llm_provider=llm_provider, llm_model=llm_model)

    # Default to markdown files only
    if include is None:
        include = ["**/*.md", "**/*.markdown"]

    reader = _build_document_reader(
        paths, 
        include, 
        exclude or [], 
        recursive, 
        max_files
    )
    documents = reader.load_data()
    
    if not documents:
        return {"warning": "No documents loaded after filtering."} if return_stats else None

    storage = _create_faiss_storage(index_dir)
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage,
        show_progress=True,
        store_nodes=True,
    )
    _persist_index(storage, index_dir)

    return _generate_stats(documents, index) if return_stats else None
