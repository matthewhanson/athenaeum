# API Reference

Athenaeum provides a FastAPI-based REST API for document retrieval and question answering. The server can be run locally or deployed to AWS Lambda.

## Base URL

- **Local Development:** `http://localhost:8000`
- **AWS Lambda:** `https://your-api.execute-api.region.amazonaws.com/prod`

## Endpoints

### `GET /`

Landing page with API documentation and endpoint discovery.

**Response:**

```json
{
  "name": "Athenaeum API Server",
  "version": "0.1.0",
  "description": "REST API for RPG knowledge base retrieval",
  "endpoints": [
    {
      "path": "/health",
      "method": "GET",
      "description": "Health check endpoint"
    },
    {
      "path": "/models",
      "method": "GET",
      "description": "List available models"
    },
    {
      "path": "/personas",
      "method": "GET",
      "description": "List available personas"
    },
    {
      "path": "/search",
      "method": "POST",
      "description": "Search for context chunks"
    },
    {
      "path": "/chat",
      "method": "POST",
      "description": "Interactive chat with tool calling"
    }
  ]
}
```

---

### `GET /health`

Health check endpoint to verify server is running.

**Response:**

```json
{"status": "ok"}
```

---

### `GET /models`

List available retrieval models.

**Response:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "athenaeum-index-retrieval",
      "object": "model",
      "created": 1234567890,
      "owned_by": "athenaeum"
    }
  ]
}
```

---

### `GET /personas`

List available personas (system prompts).

**Response:**

```json
{
  "personas": [
    {
      "id": "andraax",
      "name": "Andraax",
      "file": "andraax_system_prompt.md"
    },
    {
      "id": "scribe",
      "name": "Scribe",
      "file": "scribe_system_prompt.md"
    }
  ],
  "default": "scribe"
}
```

---

### `POST /search`

Search for relevant context chunks. Returns raw vector search results without answer generation.

**Use Case:** Building custom RAG applications, debugging retrieval, or when you want to handle answer generation yourself.

**Request:**

```json
{
  "query": "What are Dragonlords?",
  "limit": 5
}
```

**Parameters:**
- `query` (string, required): Search query
- `limit` (integer, optional): Number of results (default: 5)

**Response:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "doc1.txt",
      "content": "Dragonlords were ancient sorcerers...",
      "metadata": {
        "path": "lore/history.md",
        "score": 0.95
      }
    },
    {
      "id": "doc2.txt",
      "content": "The first Dragonlord appeared in...",
      "metadata": {
        "path": "lore/timeline.md",
        "score": 0.89
      }
    }
  ],
  "model": "athenaeum-index-retrieval",
  "usage": {
    "total_tokens": 0
  }
}
```

---

### `POST /chat`

Interactive chat endpoint with autonomous tool calling. The LLM can search multiple times to build comprehensive answers.

**Use Case:** Primary endpoint for interactive applications. LLM automatically decides when and how many times to search.

**Request:**

```json
{
  "messages": [
    {"role": "user", "content": "Tell me about the Wars of Dominion"}
  ],
  "model": "gpt-4o-mini",
  "temperature": 0.7,
  "max_tokens": 512,
  "persona": "andraax",
  "skip_classification": false
}
```

**Parameters:**
- `messages` (array, required): Chat history with role and content
- `model` (string, optional): OpenAI model (default: "gpt-4o-mini")
- `temperature` (float, optional): Sampling temperature (default: 0.7)
- `max_tokens` (integer, optional): Max response tokens (default: 512)
- `persona` (string, optional): Persona to use (loads `{persona}_system_prompt.md`)
- `skip_classification` (boolean, optional): Bypass classification (default: false)

**Response:**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The Wars of Dominion were a series of conflicts..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 200,
    "total_tokens": 350
  },
  "tool_calls_made": 2,
  "tool_calls": [
    {
      "id": "call_abc",
      "type": "function",
      "function": {
        "name": "search_knowledge_base",
        "arguments": "{\"query\": \"Wars of Dominion\", \"limit\": 5}"
      }
    }
  ],
  "classification": "PUBLIC"
}
```

**Response Fields:**
- `tool_calls_made` (integer): Number of searches performed
- `tool_calls` (array): Details of each tool call made
- `classification` (string): Classification level if enabled (PUBLIC/GUARDED/FORBIDDEN/null)

---

## Tool Calling

The `/chat` endpoint includes tools that the LLM can call autonomously:

### `search_knowledge_base`

Search the indexed documents for relevant information.

**When LLM uses it:** When it needs specific information to answer your question.

**Parameters:**
- `query` (string): Search query
- `limit` (integer): Max results (default: 5)

**Example:** User asks "What are Dragonlords?" → LLM calls `search_knowledge_base` with query "Dragonlords history and abilities"

---

### `search_timeline`

Search timeline entries within a specific year range.

**When LLM uses it:** For questions about date ranges, historical periods, or time-based queries.

**Parameters:**
- `start_year` (integer, optional): Starting year (inclusive). Omit for "before year X" queries.
- `end_year` (integer, optional): Ending year (inclusive). Omit for "after year X" queries.
- `limit` (integer, optional): Max results (default: 10)

**Features:**
- Numerical year filtering (not semantic search)
- Chronological sorting
- Open-ended ranges supported
- Works with any metadata containing year information

**Example:**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "What major events happened between years 1000-2000?"
      }
    ],
    "persona": "historian"
  }'
```

The LLM will automatically call `search_timeline` with `start_year: 1000` and `end_year: 2000`.

---

## Personas

Personas are system prompts that define how the AI responds. Switch personas per-request to change the AI's behavior without redeployment.

### Creating Personas

**1. Create a persona file:** `{persona_name}_system_prompt.md`

```markdown
You are Eldrin the Sage, keeper of the ancient archives.
You speak formally and refer to historical events you've witnessed.
When asked about forbidden knowledge, deflect:
"That knowledge is restricted to the Council..."
```

**2. Place in prompts directory:**

```
prompts/
├── classification_prompt.txt       # Optional: classification rules
├── eldrin_system_prompt.md         # Persona 1
├── guard_system_prompt.md          # Persona 2
└── librarian_system_prompt.md      # Persona 3
```

**3. Deploy to Lambda:**

```dockerfile
# Copy all persona prompts
COPY prompts/*_system_prompt.md /var/task/

# Set default persona (optional)
ENV CHAT_SYSTEM_PROMPT_FILE=/var/task/librarian_system_prompt.md
ENV CHAT_SYSTEM_PROMPT_DIR=/var/task
```

### Using Personas

**Specify persona in request:**

```json
{
  "messages": [{"role": "user", "content": "Tell me about the war"}],
  "persona": "eldrin"
}
```

**Persona Resolution Order:**
1. Request `persona` parameter → loads `{persona}_system_prompt.md`
2. `CHAT_SYSTEM_PROMPT_FILE` env var → deployment default
3. `CHAT_SYSTEM_PROMPT` env var → direct prompt text
4. Base athenaeum prompt → minimal fallback

**Benefits:**
- Switch AI behavior at request time
- Support multiple use cases with one deployment
- No redeployment needed to add personas

---

## Classification

Optional pre-classification of questions to control information disclosure. Useful for guarding campaign secrets or sensitive lore.

### How It Works

**Enable:** Create `prompts/classification_prompt.txt`

If this file exists, ALL questions are classified BEFORE RAG retrieval:

- **PUBLIC**: Full RAG retrieval (top_k=5), answer with detail
- **GUARDED**: Limited RAG (top_k=2), answer but stay vague
- **FORBIDDEN**: No RAG retrieval, deflect in character

**Bypass:** Set `skip_classification: true` in request

### Classification Prompt Example

```
You are a knowledge classifier for a fantasy RPG setting.

Classify this question into ONE category:

PUBLIC - Answer freely with full detail:
- Geography, basic history, common creatures
- Public information available to players
- General world-building content

GUARDED - Answer but be vague on specifics:
- Artifact names (OK) but not their powers (NO)
- Creature existence (OK) but not detailed abilities (NO)
- Political intrigues (acknowledge but don't reveal details)

FORBIDDEN - Acknowledge only, deflect all details:
- Artifact creation methods
- Summoning or control rituals
- Plot twists and campaign secrets
- Hidden identities

Question: {question}

Classification (reply with exactly one word: PUBLIC, GUARDED, or FORBIDDEN):
```

### Response with Classification

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "*grows cold* That knowledge should remain buried."
    }
  }],
  "classification": "FORBIDDEN",
  "tool_calls_made": 0
}
```

**Note:** Classification is universal (same rules for all), but each persona deflects FORBIDDEN topics in their own character.

### Benefits

- **Prevents leakage:** Don't retrieve what shouldn't be shared
- **Fast:** ~200ms classification call (gpt-4o-mini)
- **Cost-effective:** FORBIDDEN questions cheaper (no RAG retrieval)
- **Opt-in:** Backward compatible (no file = disabled)
- **Debuggable:** Classification level in response metadata

---

## Environment Variables

Configure the API server with these environment variables:

```bash
# Required
export OPENAI_API_KEY="sk-..."              # OpenAI API key for chat/answer

# Index Location
export ATHENAEUM_INDEX_DIR="/path/to/index" # Index directory path
# or
export INDEX_DIR="/path/to/index"           # Alternative name

# Persona Configuration
export CHAT_SYSTEM_PROMPT_DIR="/var/task"   # Directory with persona files
export CHAT_SYSTEM_PROMPT_FILE="/var/task/default_system_prompt.md"  # Default persona
# or
export CHAT_SYSTEM_PROMPT="You are..."      # Direct prompt text

# Optional
export OPENAI_MODEL="gpt-4o-mini"           # Override default model
```

**Lambda Defaults:**
- `INDEX_DIR` defaults to `/var/task/index` (baked into container)
- `CHAT_SYSTEM_PROMPT_DIR` defaults to `/var/task`

---

## Example Usage

### Basic Search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What are Dragonlords?", "limit": 3}'
```

### Chat with Persona

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Tell me about the ancient wars"}
    ],
    "persona": "historian",
    "temperature": 0.7
  }'
```

### Timeline Query

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What happened between years 500-1000?"}
    ]
  }'
```

### Skip Classification (Admin/Debug)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "How was the Shadowstone created?"}
    ],
    "persona": "guardian",
    "skip_classification": true
  }'
```

---

## OpenAPI Documentation

Interactive API documentation available at:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

---

## Error Responses

All endpoints return standard HTTP status codes:

- `200 OK` - Successful request
- `400 Bad Request` - Invalid parameters
- `404 Not Found` - Endpoint or resource not found
- `500 Internal Server Error` - Server error

**Error Format:**

```json
{
  "error": "Description of what went wrong"
}
```

Common errors:
- Missing `OPENAI_API_KEY` environment variable
- Index directory not found
- Invalid persona name
- Malformed request body
