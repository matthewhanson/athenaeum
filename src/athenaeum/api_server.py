"""
FastAPI server for Athenaeum RAG system.

Provides REST API endpoints for web UIs and direct HTTP access:
- /search: Search for relevant passages (raw vector search)
- /answer: Single-search RAG (simple, fast answers)
- /chat: Interactive chat with autonomous tool calling (multi-search capability)
- /health, /models: Status and metadata endpoints
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from athenaeum.retriever import query_index, retrieve_context

# Get version from package metadata
try:
    from importlib.metadata import version
    __version__ = version("athenaeum")
except Exception:
    __version__ = "0.1.0"  # Fallback for development

# Initialize FastAPI app
# API Gateway proxy integration handles path routing automatically
# Works with both custom domain and /prod stage
app = FastAPI(
    title="Athenaeum API Server",
    description="REST API for RPG knowledge base retrieval and chat",
    version=__version__,
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
    # Dynamically detect base path from request headers
    # This works with both custom domains (no prefix) and API Gateway (with /prod or other stage)
    base_url = str(request.base_url).rstrip("/")
    
    # Check for API Gateway stage prefix in headers
    stage_prefix = ""
    if "x-forwarded-prefix" in request.headers:
        # API Gateway sets this header with the stage name
        stage_prefix = request.headers["x-forwarded-prefix"]
    
    return {
        "name": "Athenaeum API Server",
        "version": "0.1.0",
        "description": "REST API for retrieving from a custom RPG knowledge base using RAG",
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
                "path": f"{stage_prefix}/answer",
                "method": "POST",
                "description": "Generate a single answer using RAG (one search, direct response)",
                "parameters": {
                    "messages": "Array of chat messages with role and content",
                    "model": "Model name (default: gpt-4o-mini)",
                    "temperature": "Sampling temperature (default: 0.7)",
                    "max_tokens": "Maximum tokens in response (default: 512)",
                },
            },
            {
                "path": f"{stage_prefix}/chat",
                "method": "POST",
                "description": "Interactive chat with tool calling - LLM can search multiple times as needed",
                "parameters": {
                    "messages": "Array of chat messages with role and content",
                    "model": "Model name (default: gpt-4o-mini)",
                    "temperature": "Sampling temperature (default: 0.7)",
                    "max_tokens": "Maximum tokens in response (default: 512)",
                },
                "note": "LLM autonomously decides when and how many times to search the knowledge base",
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


@app.post("/answer")
def answer(request: ChatRequest, index_dir: Path = Depends(get_index_dir)) -> dict[str, Any]:
    """
    Answer endpoint with RAG - performs a single search and returns a direct answer.

    This endpoint does one RAG search and generates an answer.
    For interactive chat with multiple searches, use /chat instead.
    System prompt can be customized via CHAT_SYSTEM_PROMPT environment variable.
    """
    # Get optional system prompt from environment
    system_prompt = os.getenv("CHAT_SYSTEM_PROMPT")
    
    # Extract user query from the last user message
    user_message = None
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg
            break

    if not user_message:
        return {"error": "No user message found in the chat history"}

    # Query the index using OpenAI with optional system prompt
    result = query_index(
        index_dir=index_dir,
        question=user_message.content,
        top_k=10,
        llm_provider="openai",
        llm_model=request.model,
        system_prompt=system_prompt,
    )

    # Format as OpenAI-compatible response
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


@app.post("/chat")
def chat(request: ChatRequest, index_dir: Path = Depends(get_index_dir)) -> dict[str, Any]:
    """
    Interactive chat endpoint with autonomous tool calling.
    
    The LLM can decide when and how many times to call the search tool to answer questions.
    This enables multi-step reasoning where the LLM can:
    - Search for initial information
    - Search for related information based on what it found
    - Make multiple searches to gather comprehensive context
    
    For simple single-search RAG, use /answer instead.
    """
    try:
        from openai import OpenAI
    except ImportError:
        return {"error": "OpenAI package not installed. Run: pip install openai"}
    
    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY environment variable not set"}
    
    client = OpenAI(api_key=api_key)
    
    # Define the search tool for the LLM
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge_base",
                "description": "Search the indexed markdown documents for relevant information. Use this when you need specific information from the knowledge base to answer a question.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant passages"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]
    
    # Get system prompt from environment or use default
    system_prompt = os.getenv(
        "CHAT_SYSTEM_PROMPT",
        "You are a helpful assistant with access to a knowledge base. Use the search_knowledge_base tool to find relevant information when needed."
    )
    
    # Build messages with system prompt
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend([{"role": msg.role, "content": msg.content} for msg in request.messages])
    
    # Tool calling loop - allow up to 5 iterations to prevent infinite loops
    max_iterations = 5
    for iteration in range(max_iterations):
        # Call LLM with tools
        response = client.chat.completions.create(
            model=request.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        
        assistant_message = response.choices[0].message
        
        # Check if LLM wants to call a tool
        if not assistant_message.tool_calls:
            # No tool calls - LLM has the final answer
            return {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": assistant_message.content},
                        "finish_reason": response.choices[0].finish_reason,
                    }
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "tool_calls_made": iteration,  # Track how many search calls were made
            }
        
        # Add assistant message with tool calls to conversation
        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                }
                for tc in assistant_message.tool_calls
            ]
        })
        
        # Execute each tool call
        for tool_call in assistant_message.tool_calls:
            if tool_call.function.name == "search_knowledge_base":
                # Parse arguments
                import json
                args = json.loads(tool_call.function.arguments)
                query = args.get("query", "")
                limit = args.get("limit", 5)
                
                # Execute search
                contexts = retrieve_context(index_dir=index_dir, question=query, top_k=limit)
                
                # Format results
                results = []
                for ctx in contexts:
                    results.append({
                        "content": ctx["content"],
                        "source": ctx["metadata"].get("path", "unknown"),
                        "score": ctx.get("score", 0.0)
                    })
                
                # Add tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(results, indent=2)
                })
    
    # If we hit max iterations, return what we have
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Maximum tool call iterations reached."},
                "finish_reason": "length",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "tool_calls_made": max_iterations,
    }
