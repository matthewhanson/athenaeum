"""
MCP (Model Completion Protocol) server implementation for RAG using LlamaIndex.

This file provides both:
1. REST API endpoints for the web UI (/search, /chat, etc.)
2. MCP protocol over SSE for GitHub Copilot and other MCP clients
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.routing import Mount

from athenaeum.retriever import query_index, retrieve_context

# Detect if running in AWS Lambda and set root_path for API Gateway stage
# This ensures /docs and /openapi.json work correctly behind API Gateway
root_path = ""
if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    # Running in Lambda - assume /prod stage (can be overridden with ROOT_PATH env var)
    root_path = os.getenv("ROOT_PATH", "/prod")

# Initialize FastAPI app
app = FastAPI(
    title="Athenaeum MCP Server",
    description="Give your LLM a library - An MCP-compatible API for document retrieval",
    version="0.1.0",
    root_path=root_path,  # Set root path for API Gateway stage support
)

# Configure CORS to allow requests from browser-based clients
# Must be configured here (not just in API Gateway) because Lambda proxy
# integration passes through the response from FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins - consider restricting in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers to the browser
)


# Models for API requests and responses
class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 512


def get_index_dir() -> Path:
    """Get the index directory from environment variable or default.

    In Lambda container deployment, index is baked into image at /var/task/index.
    """
    # Check env vars first, then default to Lambda container location
    index_dir = Path(
        os.getenv("INDEX_DIR")
        or os.getenv("ATHENAEUM_INDEX_DIR")
        or "/var/task/index"  # Default for Lambda container deployment
    )
    if not index_dir.exists():
        raise FileNotFoundError(f"Index directory not found: {index_dir}")
    return index_dir


@app.get("/")
def landing_page(request: Request) -> dict[str, Any]:
    """Landing page with API documentation and endpoint links."""
    # Detect base path from API Gateway stage
    # Lambda Web Adapter sets AWS_LAMBDA_FUNCTION_NAME, use that to detect Lambda environment
    # In API Gateway with stages, the full path includes the stage (e.g., /prod)
    base_url = str(request.base_url).rstrip("/")
    
    # Try to get the stage from headers or path
    stage_prefix = ""
    if "x-forwarded-prefix" in request.headers:
        stage_prefix = request.headers["x-forwarded-prefix"]
    elif request.scope.get("root_path"):
        stage_prefix = request.scope["root_path"]
    
    # Default to /prod for AWS deployments if we can't detect it
    if not stage_prefix and os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        stage_prefix = "/prod"
    
    return {
        "name": "Athenaeum MCP Server",
        "version": "0.1.0",
        "description": "An MCP-compatible API for retrieving from a custom knowledge base using RAG",
        "base_url": base_url + stage_prefix if stage_prefix else base_url,
        "endpoints": [
            {
                "path": f"{stage_prefix}/health",
                "method": "GET",
                "description": "Health check endpoint to verify the server is running",
            },
            {"path": f"{stage_prefix}/models", "method": "GET", "description": "List available models"},
            {
                "path": f"{stage_prefix}/search",
                "method": "POST",
                "description": "Search for context chunks matching a query for RAG applications",
                "parameters": {
                    "query": "The search query string",
                    "limit": "Number of results to return (default: 5)",
                },
            },
            {
                "path": f"{stage_prefix}/chat",
                "method": "POST",
                "description": "Generate an answer using the index and RAG",
                "parameters": {
                    "messages": "Array of chat messages with role and content",
                    "model": "Model name (default: gpt-4o-mini)",
                    "temperature": "Sampling temperature (default: 0.7)",
                    "max_tokens": "Maximum tokens in response (default: 512)",
                },
            },
        ],
        "documentation": f"{stage_prefix}/docs",
        "openapi": f"{stage_prefix}/openapi.json",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/models")
def list_models() -> dict[str, Any]:
    """List available models endpoint."""
    return {
        "object": "list",
        "data": [
            {
                "id": "athenaeum-index-retrieval",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "athenaeum",
            }
        ],
    }


@app.post("/search")
def search(request: SearchRequest, index_dir: Path = Depends(get_index_dir)) -> dict[str, Any]:
    """
    Search endpoint for RAG.

    This endpoint returns context chunks matching the query for use in RAG applications.
    """
    contexts = retrieve_context(index_dir=index_dir, question=request.query, top_k=request.limit)

    documents = []
    for ctx in contexts:
        documents.append(
            {"id": ctx["metadata"]["path"], "content": ctx["content"], "metadata": ctx["metadata"]}
        )

    return {
        "object": "list",
        "data": documents,
        "model": "athenaeum-index-retrieval",
        "usage": {
            "total_tokens": 0  # Token counting not implemented
        },
    }


@app.post("/chat")
def chat(request: ChatRequest, index_dir: Path = Depends(get_index_dir)) -> dict[str, Any]:
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
        return {"error": "No user message found in the chat history"}

    # Query the index using OpenAI
    result = query_index(
        index_dir=index_dir,
        question=user_message.content,
        top_k=5,
        llm_provider="openai",
        llm_model=request.model,
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
                "message": {"role": "assistant", "content": result["answer"]},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


# Mount MCP protocol SSE endpoint for GitHub Copilot and other MCP clients
# This is imported conditionally to avoid errors when MCP SDK is not installed
try:
    from athenaeum.mcp_protocol import mcp
    
    # Mount the SSE server at /mcp for MCP protocol support
    # GitHub and other MCP clients will connect to this endpoint
    app.router.routes.append(Mount("/mcp", app=mcp.sse_app()))
except ImportError:
    # MCP SDK not installed - SSE endpoint will not be available
    # The REST API endpoints will still work for the web UI
    pass
