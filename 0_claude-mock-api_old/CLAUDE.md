# Claude Mock API Server (Multi-Format Support)

## Overview

This is a **dual-format** mock Python API server that supports both:
1. **Anthropic Messages API** (`/v1/messages`) — Claude's native format ⭐ **Recommended**
2. **OpenAI Chat Completions** (`/v1/chat/completions`) — For backward compatibility

The server is protected by a configurable mock API key and provides a **100% drop-in replacement** for AI Agent frameworks like **LangChain**, **LlamaIndex**, **AutoGen**, and **CrewAI**. In the backend, the server executes the local **Claude CLI** (`claude --print`) running on the host machine.

### Architecture

```
AI Agent / LangChain / Client
       │ (Anthropic Messages API OR OpenAI format)
       │ (x-api-key OR Authorization: Bearer)
       ▼
FastAPI Server (localhost:8000)
       │ (Extracts messages & system prompt)
       ▼
Claude CLI subprocess (`claude --print`)
       │
       ▼
Claude Engine (uses host's Claude session)
```

## Project Structure

```
claude-mock-api/
├── CLAUDE.md                  # This file — Project documentation for Claude Code
├── README.md                  # User-facing documentation & integration guide
├── PROJECT_SUMMARY.md         # Project completion summary & quick reference
├── examples.py                # Working LangChain/OpenAI SDK integration examples
├── requirements.txt           # Core Python dependencies
├── requirements-examples.txt  # Optional dependencies for examples.py
├── .env.example               # Template for environment variables
├── .env                       # Local env vars (git-ignored)
├── start-server.bat           # Windows launcher (creates .venv, installs deps, starts app)
├── stop-server.bat            # Windows script to stop the server
├── .venv/                     # Virtual environment (git-ignored)
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI app entry point
│   ├── config.py              # Settings & API key management
│   ├── auth.py                # Dual auth: x-api-key OR Bearer token
│   ├── routes/
│   │   ├── __init__.py
│   │   └── chat.py            # /v1/messages & /v1/chat/completions endpoints
│   └── services/
│       ├── __init__.py
│       ├── claude_cli.py      # Claude CLI wrapper with dual format support
│       └── tool_simulator.py  # Deterministic tool-use loop engine
└── tests/
    ├── __init__.py
    ├── test_chat.py           # Compatibility & unit tests
    └── test_tool_use.py       # Agentic tool-use loop tests
```

## Commands

### Windows (Recommended)

```cmd
# Start the server (handles venv creation, activation, and dependency installation)
start-server.bat

# Stop the server
stop-server.bat

# Manual start (if start-server.bat doesn't work)
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run tests
.venv\Scripts\activate && pytest tests/ -v
```

### Manual (Cross-platform)

```bash
# Activate venv & install deps
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or with Python module
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## AI Agent / LangChain Integration

### 1. LangChain with Claude Native API (Recommended) ⭐

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# Connect to our local mock API using Anthropic's native format
llm = ChatAnthropic(
    anthropic_api_url="http://localhost:8000",  # Base URL (SDK adds /v1/messages)
    anthropic_api_key="mock-api-key-001",       # Mock API key
    model_name="claude-3-5-sonnet-20241022"     # Claude model
)

response = llm.invoke([
    SystemMessage(content="You are a helpful research assistant."),
    HumanMessage(content="Explain what an AI agent is in two sentences.")
])

print(response.content)
```

**Why use Claude native format?**
- ✅ More authentic API experience
- ✅ Better Claude feature support
- ✅ Cleaner API semantics (separate `system` parameter)
- ✅ Future-ready for new Claude features

### 2. LangChain with OpenAI Format (Legacy/Compatibility)

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# Connect using OpenAI-compatible format
llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="mock-api-key-001",
    model="claude"
)

response = llm.invoke([
    SystemMessage(content="You are a helpful research assistant."),
    HumanMessage(content="Explain what an AI agent is in two sentences.")
])

print(response.content)
```

### 3. Anthropic Python SDK

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://localhost:8000",
    api_key="mock-api-key-001"
)

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)

print(response.content[0].text)
```

### 4. OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="mock-api-key-001"
)

response = client.chat.completions.create(
    model="claude",
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response.choices[0].message.content)
```

## Tool Use / Agentic Loop Support ⭐

The `/v1/messages` endpoint **simulates a full Anthropic tool-use loop**, so a
client agent (e.g. LangChain `ChatAnthropic`) can demonstrate the complete
`request → tool_use → tool_result → request → tool_use → ... → end_turn`
flow against this mock — no real Anthropic API required.

### How it works

The server is stateless and derives every decision from the incoming request:

1. **Tools** — read from the request's `tools` array (names + JSON schemas).
2. **State** — scans the assistant history for `tool_use` blocks to know which
   tools have already been called.
3. **Relevance** — matches the *original* user question against tool names and
   descriptions to pick the next tool.
4. **Decision per turn:**
   - A relevant tool not yet called → return a `tool_use` block,
     `stop_reason="tool_use"`.
   - No relevant tool left → return a synthesized text answer built from the
     collected `tool_result` blocks, `stop_reason="end_turn"`.

Tool-call arguments are generated to match the provided `input_schema`
(required fields always filled; string/number/bool/array handled generically),
so it works with **any** tool set, not a hard-coded example.

### What the client sees

| Turn | Client sends | Server returns | `stop_reason` |
|---|---|---|---|
| 1 | task + `tools` | `[tool_use]` | `tool_use` |
| 2 | task + `tool_result` | `[tool_use]` (next tool) or `[text]` | `tool_use` / `end_turn` |
| 3+ | ... | ... | ... |

### LangChain agent example

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    anthropic_api_url="http://localhost:8000",
    anthropic_api_key="mock-api-key-001",
    model_name="claude-3-5-sonnet-20241022",
    tools=[get_weather, get_timezone],
)

# The agentic loop is driven by the client: keep sending until
# response.response_metadata["stop_reason"] == "end_turn".
```

> Implementation lives in `app/services/tool_simulator.py`
> (`ToolUseSimulator`) and is wired into `ask_claude_messages` in
> `app/services/claude_cli.py`. Server logs show each decision
> (request received, tools available, selected tool + args, tool results,
> and whether it returns `tool_use` or `end_turn`).

## Switching Between Formats

### To Real Claude API (Anthropic)

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    # Remove anthropic_api_url -> uses https://api.anthropic.com
    anthropic_api_key="sk-ant-...",  # Real Anthropic API key
    model_name="claude-3-5-sonnet-20241022"
)
```

### To Real OpenAI API

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    # Remove base_url -> uses https://api.openai.com/v1
    api_key="sk-proj-...",  # Real OpenAI API key
    model="gpt-4o"
)
```

## API Endpoints

| Method | Endpoint | Format | Description |
|---|---|---|---|
| `POST` | `/v1/messages` | **Anthropic** ⭐ | Claude native Messages API (recommended) |
| `POST` | `/v1/chat/completions` | OpenAI | OpenAI-compatible chat completion |
| `GET` | `/v1/models` | OpenAI | List available models for SDK discovery |
| `POST` | `/v1/chat` | Simple | Single-message endpoint (legacy) |
| `GET` | `/health` | - | Server health check (no auth required) |
| `POST` | `/admin/rotate-key` | - | Rotate the mock API key |

### Authentication Methods

Both methods work for all endpoints:

1. **Anthropic Style** (recommended): `x-api-key: <key>` header
2. **OpenAI Style**: `Authorization: Bearer <key>` header

## Request/Response Formats

### Anthropic Messages API (`/v1/messages`)

**Request:**
```json
{
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 1024,
  "system": "You are a helpful assistant.",
  "messages": [
    {"role": "user", "content": "Hello"}
  ]
}
```

**Response:**
```json
{
  "id": "msg_01XYZ...",
  "type": "message",
  "role": "assistant",
  "model": "claude-3-5-sonnet-20241022",
  "content": [
    {"type": "text", "text": "Hello! How can I help you?"}
  ],
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 25,
    "output_tokens": 12
  }
}
```

### OpenAI Chat Completions (`/v1/chat/completions`)

**Request:**
```json
{
  "model": "claude",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello"}
  ],
  "max_tokens": 1024
}
```

**Response:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "claude",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 12,
    "total_tokens": 37
  }
}
```

## Tech Stack

- **Python 3.10+**
- **FastAPI** — async web framework
- **Uvicorn** — ASGI server with auto-reload
- **Pydantic** — request/response validation
- **python-dotenv** — environment variable loading
- **subprocess** — to invoke `claude` CLI

## Key Design Decisions

1. **Dual Format Support** — Both Anthropic native and OpenAI formats for maximum compatibility

2. **Dual Authentication** — Accept both `x-api-key` header (Anthropic) and `Authorization: Bearer` (OpenAI)

3. **Mock API key, not real Anthropic key** — The server owns a local mock key (set in `.env`). Users hit this server with that key. The server itself calls `claude` CLI which uses whatever Claude authentication is configured on the host.

4. **Claude CLI as backend** — Instead of calling the Anthropic API directly, we shell out to `claude --print` so we leverage the same Claude Code session the developer uses interactively.

5. **Robust stderr handling** — Claude CLI may write warnings to stderr even on success. We only fail if stdout is empty.

6. **Streaming support** — Both blocking and streaming (`stream: true`) responses via Server-Sent Events for both formats.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MOCK_API_KEY` | `mock-api-key-001` | The API key users must send in `x-api-key` or `Authorization: Bearer <key>` |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `CLAUDE_CLI_PATH` | `claude` | Path to the Claude CLI binary (assumes it's on PATH) |
| `MAX_TOKENS` | `4096` | Default max tokens for responses (note: Claude CLI doesn't support --max-tokens) |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins (comma-separated) |

## Running the Examples

```bash
# Install example dependencies
pip install -r requirements-examples.txt

# Run the integrated examples
python examples.py
```

The `examples.py` file demonstrates:
- LangChain ChatAnthropic (Anthropic native format)
- LangChain ChatOpenAI (OpenAI format)
- Anthropic Python SDK usage
- OpenAI Python SDK usage
- Multi-turn conversations
- Streaming responses
- How to switch to production APIs

## Important Notes

### Claude CLI Limitations

1. **No `--max-tokens` support** — The `max_tokens` parameter is accepted for API compatibility but not passed to Claude CLI. Response length is controlled by Claude's default behavior.

2. **Stderr warnings** — Claude CLI may write warnings to stderr (e.g., about unrecognized models) even when producing valid output. The server handles this gracefully.

3. **Session context** — Each `claude --print` call is stateless. For conversation memory, the caller must manage message history.

## Conventions

- Use `async def` for all route handlers.
- Type-hint all function signatures.
- Keep route handlers thin — business logic goes in `app/services/`.
- Use Pydantic models for request/response validation.
- Log with `logging` stdlib, not `print`.
- Return standard format objects (Anthropic `message` or OpenAI `chat.completion`).

## Troubleshooting

### Server won't start (port 8000 in use)

```bash
# Find and kill process on port 8000 (Windows)
netstat -ano | findstr :8000
taskkill /F /PID <PID>

# Or use a different port
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### "Invalid API key" errors

Check that your client's API key matches `MOCK_API_KEY` in `.env`:
```bash
# Default is:
MOCK_API_KEY=mock-api-key-001
```

### Claude CLI errors

The server logs Claude CLI stderr. Check the uvicorn console output for warnings.

Common issues:
- Claude CLI not in PATH → Set `CLAUDE_CLI_PATH` in `.env`
- Claude not authenticated → Run `claude auth` first

## Next Steps

See `../1_1_Agentic_Loops/` for agent examples that use this server!

---

**Note**: This server is designed for local development and learning. Not suitable for production use.
