"""
MCP Protocol implementation using the official SDK.

This provides the Model Context Protocol over SSE transport,
which can be used alongside the existing REST API.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from athenaeum.retriever import retrieve_context


def get_index_dir() -> Path:
    """Get the index directory from environment variable or use default."""
    index_dir = os.getenv("INDEX_DIR", "./index")
    return Path(index_dir)


# Create FastMCP server instance
# This implements the Model Context Protocol over SSE
mcp = FastMCP(
    name="Athenaeum",
    instructions="A RAG system for querying markdown documentation. Use the search tool to find relevant passages from the indexed documents.",
)


@mcp.tool()
def search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search the indexed documents for relevant passages.
    
    Args:
        query: The search query
        limit: Maximum number of results to return (default: 10)
    
    Returns:
        List of search results with content, metadata, and scores
    """
    index_dir = get_index_dir()
    
    if not index_dir.exists():
        return []
    
    results = retrieve_context(str(index_dir), query, limit)
    
    return [
        {
            "id": r.get("metadata", {}).get("path", "unknown"),
            "content": r.get("content", ""),
            "score": r.get("metadata", {}).get("score", 0.0),
            "metadata": r.get("metadata", {}),
        }
        for r in results
    ]


@mcp.resource("index://status")
def index_status() -> str:
    """Get the status of the current index."""
    index_dir = get_index_dir()
    
    if not index_dir.exists():
        return f"Index directory does not exist: {index_dir}"
    
    # Check for required index files
    required_files = [
        "faiss.index",
        "docstore.json",
        "index_store.json",
        "default__vector_store.json",
    ]
    
    status_parts = [f"Index directory: {index_dir}"]
    
    for file in required_files:
        file_path = index_dir / file
        if file_path.exists():
            size = file_path.stat().st_size
            status_parts.append(f"✓ {file} ({size:,} bytes)")
        else:
            status_parts.append(f"✗ {file} (missing)")
    
    return "\n".join(status_parts)
