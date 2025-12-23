"""
Business logic for building FAISS-backed vector indexes using LlamaIndex.
Optimized for markdown documents with structure-aware parsing.
"""

from __future__ import annotations

import contextlib
import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import faiss
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import Document, TextNode
from llama_index.vector_stores.faiss import FaissVectorStore

from athenaeum.utils import setup_settings

# ============================================================================
# Hierarchical Context Preservation
# ============================================================================


def _looks_like_year_or_date(text: str) -> tuple[bool, str]:
    """
    Detect if a heading looks like a year/date and enhance it with temporal keywords.
    
    Handles various timeline formats:
    - "6050" -> (True, "Year 6050")
    - "6050-3-14" -> (True, "Date 6050-3-14")
    - "c. 1300" -> (True, "circa Year 1300")
    - "1066 – 1087" -> (True, "Years 1066 – 1087")
    - "Installation" -> (False, "Installation")
    
    This helps semantic search by adding natural language temporal keywords
    that match queries like "what happened in year 6050" or "events in 1066".
    """
    text = text.strip()
    
    # Check for range: "1066 – 1087" or "1-1000"
    if '–' in text or '—' in text:
        # Likely a year range
        return (True, f"Years {text}")
    
    # Check for "c." prefix (circa)
    if text.startswith('c.'):
        return (True, f"circa Year {text[2:].strip()}")
    
    # Check if it's purely numeric or date-like (year, year-month, year-month-day)
    # Strip leading/trailing non-digits
    clean = text.strip('.,;:!? ')
    
    # Pattern: digits with optional dashes (6050, 6050-3, 6050-3-14)
    if re.match(r'^\d+(-\d+)*$', clean):
        # Has dashes - likely a date
        if '-' in clean:
            return (True, f"Date {clean}")
        else:
            # Just a number - likely a year
            return (True, f"Year {clean}")
    
    # Not a temporal heading
    return (False, text)


def _inject_breadcrumbs(documents: list[Document]) -> list[Document]:
    """
    Inject heading breadcrumbs into document text to preserve hierarchy.
    
    This solves the known LlamaIndex MarkdownNodeParser limitation where
    parent heading context is lost during chunking. By prepending breadcrumbs
    to the content, we ensure each chunk knows its hierarchical context.
    
    This is critical for hierarchical documents where the same heading text
    might appear under different parents (e.g., "Installation" under both
    "Windows" and "Linux" sections, or year "1066" under different era sections).
    
    Example transformation:
        Original markdown:
            # User Guide
            ## Installation
            ### Windows
            Follow these steps...
            
        After breadcrumb injection:
            # User Guide
            ## Installation
            [User Guide > Installation]
            
            ### Windows
            [User Guide > Installation > Windows]
            
            Follow these steps...
            
    The breadcrumb is embedded in the chunk text, improving both semantic
    search accuracy and LLM context understanding.
    """
    processed_docs = []
    
    for doc in documents:
        content = doc.text
        lines = content.split('\n')
        new_lines = []
        
        # Track heading hierarchy as we parse
        hierarchy_stack = []  # List of (level, heading_text) tuples
        
        for line in lines:
            # Check if this line is a heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                
                # Enhance temporal headings with natural language keywords
                is_temporal, enhanced_text = _looks_like_year_or_date(heading_text)
                
                # Pop headings at same or deeper level
                while hierarchy_stack and hierarchy_stack[-1][0] >= level:
                    hierarchy_stack.pop()
                
                # Store the enhanced text in hierarchy for better breadcrumbs
                hierarchy_stack.append((level, enhanced_text))
                
                # Keep the original heading
                new_lines.append(line)
                
                # Add breadcrumb on next line if we have hierarchy
                if len(hierarchy_stack) > 1:
                    # Build breadcrumb from all levels
                    breadcrumb_parts = [text for _, text in hierarchy_stack]
                    breadcrumb = " > ".join(breadcrumb_parts)
                    new_lines.append(f"[{breadcrumb}]")
                    new_lines.append("")  # Empty line for spacing
                elif is_temporal:
                    # Even at top level, add temporal context for better search
                    new_lines.append(f"[{enhanced_text}]")
                    new_lines.append("")
            else:
                # Regular content line
                new_lines.append(line)
        
        # Create new document with breadcrumb-injected content
        new_doc = Document(
            text="\n".join(new_lines),
            metadata=doc.metadata,
            excluded_embed_metadata_keys=doc.excluded_embed_metadata_keys,
            excluded_llm_metadata_keys=doc.excluded_llm_metadata_keys,
        )
        processed_docs.append(new_doc)
    
    return processed_docs


# ============================================================================
# Index Building
# ============================================================================


def _validate_paths(inputs: list[Path]) -> list[Path]:
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
    max_files: int | None,
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
    with contextlib.suppress(Exception):
        # Count total nodes in the docstore
        nodes_indexed = len(index.docstore.docs)
    return {
        "documents_ingested": num_docs,
        "index_summary": {"vector_store": "faiss", "nodes_indexed": nodes_indexed},
    }


def build_index(
    inputs: list[Path],
    index_dir: Path,
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    llm_provider: str | None = None,
    llm_model: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    recursive: bool = True,
    max_files: int | None = None,
    return_stats: bool = True,
) -> dict[str, Any] | None:
    """
    Build/update a FAISS-backed index from markdown files.

    Uses MarkdownNodeParser for structure-aware parsing that respects
    headings, code blocks, and other markdown elements.

    Uses sentence-transformers for embeddings (local, consistent).
    LLM provider is optional - only needed if you plan to use chat/generation features.
    LLM provider is configurable but only used during indexing for metadata.

    Args:
        inputs: List of markdown file paths or directories to index
        index_dir: Directory to store the index
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
    setup_settings(
        embed_model=embed_model,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )

    # Default to markdown files only
    if include is None:
        include = ["**/*.md", "**/*.markdown"]

    reader = _build_document_reader(paths, include, exclude or [], recursive, max_files)
    documents = reader.load_data()

    if not documents:
        return {"warning": "No documents loaded after filtering."} if return_stats else None

    # Inject hierarchical breadcrumbs to preserve heading context
    # This solves the MarkdownNodeParser limitation where parent headings are lost
    documents = _inject_breadcrumbs(documents)

    storage = _create_faiss_storage(index_dir)
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage,
        show_progress=True,
        store_nodes=True,
    )
    _persist_index(storage, index_dir)

    return _generate_stats(documents, index) if return_stats else None
