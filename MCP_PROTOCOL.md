# MCP Protocol Support

Athenaeum now supports the Model Context Protocol (MCP) over SSE transport, in addition to the existing REST API endpoints.

## What is MCP?

The Model Context Protocol (MCP) is a standardized way for AI applications (like GitHub Copilot) to connect to knowledge sources. It uses Server-Sent Events (SSE) for real-time communication.

## Architecture

The server provides two interfaces:

1. **REST API** (for web UI):
   - `/search` - Search the index
   - `/chat` - Ask questions with RAG
   - `/health` - Health check
   - `/models` - List available models

2. **MCP Protocol** (for GitHub Copilot, Claude Desktop, etc.):
   - `/mcp` - SSE endpoint implementing MCP protocol
   - Tools: `search`, `chat`
   - Resources: `index://status`

## Using with GitHub Copilot

To connect Athenaeum to GitHub as a connector:

### Local Development

1. Start the server locally:
   ```bash
   cd athenaeum
   source .venv/bin/activate
   uvicorn athenaeum.mcp_server:app --reload
   ```

2. The MCP endpoint will be available at: `http://localhost:8000/mcp`

3. In GitHub, add the connector:
   - URL: `http://localhost:8000/mcp`
   - The server will respond with SSE events

### AWS Lambda Deployment

When deployed to AWS Lambda with API Gateway:

1. The MCP endpoint is at: `https://your-api.execute-api.region.amazonaws.com/prod/mcp`

2. Configure GitHub with this URL

3. **Note**: API Gateway may have limitations with SSE streaming. For production MCP usage, consider:
   - Using a direct Lambda Function URL (supports streaming)
   - Deploying on ECS/Fargate with Application Load Balancer
   - Using a separate WebSocket API for real-time communication

## MCP Tools

### `search`
Search the indexed documents for relevant passages.

**Parameters:**
- `query` (string): The search query
- `limit` (integer, default: 10): Maximum number of results

**Returns:** Array of search results with content, metadata, and relevance scores

### `chat`
Ask a question and get an answer based on the indexed documents.

**Parameters:**
- `query` (string): The question to answer
- `max_tokens` (integer, default: 1024): Maximum tokens in response

**Returns:** Generated answer with source citations

## MCP Resources

### `index://status`
Get the status of the current index (file sizes, presence check).

## Testing the MCP Endpoint

### Using MCP Inspector

```bash
# Install and run MCP inspector
npx @modelcontextprotocol/inspector

# Connect to: http://localhost:8000/mcp
```

### Using curl (for debugging)

```bash
# The endpoint uses SSE, so you'll see event-stream responses
curl -N -H "Accept: text/event-stream" http://localhost:8000/mcp
```

## Environment Variables

- `INDEX_DIR`: Path to the FAISS index directory
- `ATHENAEUM_INDEX_DIR`: Alternative index directory path
- `AWS_LAMBDA_FUNCTION_NAME`: Auto-detected in Lambda (sets `/prod` prefix)

## Dependencies

The MCP support requires:

```toml
"mcp>=1.0.0"  # Model Context Protocol SDK
```

This is included in the main `athenaeum` dependencies.
