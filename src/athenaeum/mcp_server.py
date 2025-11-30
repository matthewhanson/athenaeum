"""
MCP (Model Completion Protocol) server implementation for RAG using LlamaIndex.
"""

from __future__ import annotations

import os
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, Depends
from pydantic import BaseModel

from athenaeum.retriever import query_index, retrieve_context

# Initialize FastAPI app
app = FastAPI(
    title="Athenaeum MCP Server",
    description="Give your LLM a library - An MCP-compatible API for document retrieval",
    version="0.1.0"
)

# Models for API requests and responses
class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 512


def get_index_dir() -> Path:
    """Get the index directory from environment variable or default."""
    index_dir = Path(os.getenv("ATHENAEUM_INDEX_DIR", "./index"))
    if not index_dir.exists():
        raise FileNotFoundError(f"Index directory not found: {index_dir}")
    return index_dir


@app.get("/")
def landing_page() -> Dict[str, Any]:
    """Landing page with API documentation and endpoint links."""
    return {
        "name": "Athenaeum MCP Server",
        "version": "0.1.0",
        "description": "An MCP-compatible API for retrieving from a custom knowledge base using RAG",
        "endpoints": [
            {
                "path": "/health",
                "method": "GET",
                "description": "Health check endpoint to verify the server is running"
            },
            {
                "path": "/models",
                "method": "GET",
                "description": "List available models"
            },
            {
                "path": "/search",
                "method": "POST",
                "description": "Search for context chunks matching a query for RAG applications",
                "parameters": {
                    "query": "The search query string",
                    "limit": "Number of results to return (default: 5)"
                }
            },
            {
                "path": "/chat",
                "method": "POST",
                "description": "Generate an answer using the index and RAG",
                "parameters": {
                    "messages": "Array of chat messages with role and content",
                    "model": "Model name (default: gpt-4o-mini)",
                    "temperature": "Sampling temperature (default: 0.7)",
                    "max_tokens": "Maximum tokens in response (default: 512)"
                }
            }
        ],
        "documentation": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/models")
def list_models() -> Dict[str, Any]:
    """List available models endpoint."""
    return {
        "object": "list",
        "data": [
            {
                "id": "athenaeum-index-retrieval",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "athenaeum"
            }
        ]
    }


@app.post("/search")
def search(request: SearchRequest, index_dir: Path = Depends(get_index_dir)) -> Dict[str, Any]:
    """
    Search endpoint for RAG.
    
    This endpoint returns context chunks matching the query for use in RAG applications.
    """
    contexts = retrieve_context(
        index_dir=index_dir,
        question=request.query,
        top_k=request.limit
    )
    
    documents = []
    for ctx in contexts:
        documents.append({
            "id": ctx["metadata"]["path"],
            "content": ctx["content"],
            "metadata": ctx["metadata"]
        })
    
    return {
        "object": "list",
        "data": documents,
        "model": "athenaeum-index-retrieval",
        "usage": {
            "total_tokens": 0  # Token counting not implemented
        }
    }


@app.post("/chat")
def chat(request: ChatRequest, index_dir: Path = Depends(get_index_dir)) -> Dict[str, Any]:
    """
    Chat endpoint with RAG.
    
    This endpoint performs RAG using the index and returns an answer.
    """
    # Extract user query from the last user message
    user_message = None
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg
            break
    
    if not user_message:
        return {
            "error": "No user message found in the chat history"
        }
    
    # Query the index using OpenAI
    result = query_index(
        index_dir=index_dir,
        question=user_message.content,
        top_k=5,
        llm_provider="openai",
        llm_model=request.model
    )
    
    # Format as MCP response
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result["answer"]
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }



