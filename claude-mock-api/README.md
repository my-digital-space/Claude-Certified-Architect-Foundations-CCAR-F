# Claude Mock API Server (OpenAI-Compatible)

A lightweight Python API server that implements the standard **OpenAI API specification** (`/v1/chat/completions` and `/v1/models`). It is designed as a **100% drop-in replacement** for AI agent frameworks like **LangChain**, **LlamaIndex**, and **CrewAI**.

Under the hood, the server proxies requests to the local **Claude CLI** (`claude --print`) session running on your machine.

---

## ⚡ Quick Start

### Option A: Windows 1-Click Launcher (Recommended)
Simply double-click:
```
start-server.bat
```
*(Automatically creates `.venv`, installs dependencies, and starts the server).*

### Option B: Manual Setup
```bash
# 1. Activate venv
.venv\Scripts\activate      # On Linux/macOS: source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🤖 AI Agent / LangChain Integration

Because this mock server implements the standard OpenAI `/v1/chat/completions` API format, you can use standard LangChain classes without any custom wrappers.

### 1. Using LangChain with this Mock Server

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# Connect to the local Claude mock server
llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="mock-api-key-change-me",
    model="claude"
)

# Invoke the agent / model
response = llm.invoke([
    SystemMessage(content="You are a helpful coding assistant."),
    HumanMessage(content="Write a Python function to reverse a string.")
])

print(response.content)
```

### 2. Switching to Real OpenAI in the Future

When you are ready to switch your AI agent to real OpenAI, **you do not need to change any logic in your code** — just change the `api_key` and remove the local `base_url`:

```python
# Real OpenAI (production)
llm = ChatOpenAI(
    api_key="sk-proj-your-real-openai-key",
    model="gpt-4o"
)
```

---

## 💻 OpenAI Python SDK Example

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="mock-api-key-change-me"
)

# Blocking call
response = client.chat.completions.create(
    model="claude",
    messages=[
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "What is Python?"}
    ]
)
print(response.choices[0].message.content)

# Streaming call
stream = client.chat.completions.create(
    model="claude",
    messages=[{"role": "user", "content": "Tell me a short story."}],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

---

## 📡 API Endpoints

| Method | Path | Auth Required | Description |
|---|---|---|---|
| `POST` | `/v1/chat/completions` | `Bearer <mock_key>` | OpenAI standard chat completion (blocking & streaming) |
| `GET` | `/v1/models` | `Bearer <mock_key>` | Model listing for LangChain / OpenAI SDK discovery |
| `POST` | `/v1/chat` | `Bearer <mock_key>` | Simplified single-message endpoint |
| `GET` | `/health` | None | Server health status |
| `POST` | `/admin/rotate-key` | `Bearer <mock_key>` | In-memory API key rotation |

---

## ⚙️ Configuration

Stored in `.env`:

| Variable | Default | Description |
|---|---|---|
| `MOCK_API_KEY` | `mock-api-key-change-me` | Bearer token required in `Authorization` header |
| `HOST` | `0.0.0.0` | Bind host |
| `PORT` | `8000` | Bind port |
| `CLAUDE_CLI_PATH` | `claude` | Path to the `claude` CLI binary |
| `MAX_TOKENS` | `4096` | Max tokens per response |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins |

---

## 🧪 Testing

```bash
.venv\Scripts\activate
pytest tests/ -v
```
