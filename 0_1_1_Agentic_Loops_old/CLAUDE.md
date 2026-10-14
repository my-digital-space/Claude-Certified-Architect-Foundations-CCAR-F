# Agentic Loops - Building AI Agents with LangChain & Claude

## Overview

This project is a step-by-step learning journey to build AI agents using **LangChain** with **Claude's native Anthropic API**. We'll explore how to create agents with tools, memory, context, and other essential components that enable autonomous behavior.

The project uses a local mock API server that provides Claude's native `/v1/messages` endpoint, allowing us to learn and experiment without incurring costs or requiring external API keys.

## Learning Path

We will progressively build AI agents, covering:

1. **Basic Agent Setup** — Understanding the agent loop and how agents reason
2. **Tool Integration** — Giving agents capabilities through custom and pre-built tools
3. **Memory Systems** — Short-term and long-term memory for context retention
4. **Context Management** — How agents maintain and use conversation context
5. **Multi-Agent Systems** — Coordinating multiple specialized agents
6. **Advanced Patterns** — ReAct, Plan-and-Execute, and other agent architectures

## Project Structure

```
1_1_Agentic_Loops/
├── CLAUDE.md                    # This file — Project documentation
├── README.md                    # User-facing documentation
├── SETUP_SUMMARY.md            # Initial setup summary
├── CLAUDE_API_MIGRATION.md     # Migration from OpenAI to Claude API
├── requirements.txt            # Python dependencies
├── .env                        # Environment configuration
├── .env.example                # Template for environment variables
├── .venv/                      # Virtual environment
├── 1_a_simple_AI_agent.py      # Simple agent example (Claude native API)
├── test_anthropic.py           # Test ChatAnthropic integration
├── test_connection.py          # API connection tester
├── examples/                   # Step-by-step examples (to be created)
├── agents/                     # Custom agent implementations (to be created)
└── tools/                      # Custom tool implementations (to be created)
```

## LLM Backend: Claude Mock API Server

We use a local mock API server that implements Claude's native Anthropic Messages API format (`/v1/messages`), which runs Claude CLI in the background.

### Mock API Server Location

```
D:\MyCode\My_GitHub\Claude-Certified-Architect-Foundations-CCAR-F\claude-mock-api
```

### Starting the Mock API Server

```bash
# Navigate to the mock API directory
cd D:\MyCode\My_GitHub\Claude-Certified-Architect-Foundations-CCAR-F\claude-mock-api

# Start the server
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# The server will be available at: http://localhost:8000
```

### Mock API Configuration

- **Base URL**: `http://localhost:8000` (Claude native) or `http://localhost:8000/v1` (OpenAI compatible)
- **API Key**: `mock-api-key-001` (default, configured in mock server's `.env`)
- **Authentication**: `x-api-key: <key>` header (Anthropic style) OR `Authorization: Bearer <key>` (OpenAI style)
- **Model**: `claude-3-5-sonnet-20241022` (Claude model identifier)

### Connecting LangChain to Mock API (Claude Native Style)

```python
from langchain_anthropic import ChatAnthropic

# Create LLM instance pointing to our local mock API (Anthropic format)
llm = ChatAnthropic(
    anthropic_api_url="http://localhost:8000",  # Base URL (SDK adds /v1/messages)
    anthropic_api_key="mock-api-key-001",       # Mock API key
    model_name="claude-3-5-sonnet-20241022"     # Claude model
)
```

### Legacy OpenAI Format (Still Supported)

The server also supports OpenAI format for backward compatibility:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="mock-api-key-001",
    model="claude"
)
```

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- Claude CLI configured on the host machine
- Mock API server running (see above)

### Environment Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Core Dependencies

We use:
- **langchain** — Core LangChain framework
- **langchain-anthropic** — Native Claude/Anthropic integration
- **langchain-core** — Core abstractions
- **anthropic** — Anthropic Python SDK
- **langchain-community** — Community tools and integrations
- **langchain-openai** — OpenAI integration (for backward compatibility)

## Learning Approach

Each example will be self-contained and progressively build on previous concepts:

1. **Run the example** — Execute the script to see the agent in action
2. **Read the code** — Understand how it's implemented with detailed comments
3. **Experiment** — Modify parameters and observe behavior changes
4. **Build your own** — Apply the concepts to create custom agents

## Key Concepts

### What is an Agentic Loop?

An agentic loop is the core reasoning cycle of an AI agent:

1. **Observe** — Receive input and current state
2. **Think** — Reason about what action to take (using Claude LLM)
3. **Act** — Execute the chosen action (use a tool, respond, etc.)
4. **Repeat** — Continue until the task is complete

### Agent Components

- **LLM (Claude)** — The language model that powers reasoning
- **Tools** — Functions the agent can call to interact with the world
- **Memory** — Storage for conversation history and learned information
- **System Prompt** — Instructions that guide agent behavior
- **Output Parser** — Extracts structured actions from LLM responses

### Claude Messages API Format

Claude's native API uses a clean, structured format:

**Request:**
```json
{
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 1024,
  "system": "You are a helpful assistant.",
  "messages": [
    {"role": "user", "content": "Hello!"}
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
  "usage": {
    "input_tokens": 25,
    "output_tokens": 12
  }
}
```

## Development Conventions

- Use type hints for all function signatures
- Keep examples focused and well-commented
- Each example should be runnable independently
- Follow LangChain best practices and patterns
- Use Claude's native API format (`ChatAnthropic`) for new code
- Document any deviations from standard approaches

## Testing Agent Behavior

```python
# Example test structure
def test_agent_response():
    """Test that agent can respond to basic queries."""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage
    
    llm = ChatAnthropic(
        anthropic_api_url="http://localhost:8000",
        anthropic_api_key="mock-api-key-001",
        model_name="claude-3-5-sonnet-20241022"
    )
    
    response = llm.invoke([HumanMessage(content="Hello!")])
    assert response.content
    assert len(response.content) > 0
```

## Switching to Production

When ready to move from learning to production:

### Option 1: Real Claude API (Anthropic)

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    # anthropic_api_url removed -> uses https://api.anthropic.com
    anthropic_api_key="sk-ant-...",  # Real Anthropic API key
    model_name="claude-3-5-sonnet-20241022"
)
```

### Option 2: OpenAI API

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    # base_url removed -> uses https://api.openai.com/v1
    api_key="sk-proj-...",  # Real OpenAI API key
    model="gpt-4o"
)
```

## API Endpoints Available

The mock server provides:

### Anthropic Native Format (Recommended)
- `POST /v1/messages` — Claude Messages API endpoint
- Authentication: `x-api-key: <key>` header

### OpenAI Compatible Format (Legacy)
- `POST /v1/chat/completions` — OpenAI chat completions
- `GET /v1/models` — List available models
- Authentication: `Authorization: Bearer <key>` header

### Utility
- `GET /health` — Server health check (no auth required)

## Resources

- [LangChain Documentation](https://python.langchain.com/)
- [LangChain Anthropic Integration](https://python.langchain.com/docs/integrations/chat/anthropic/)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Claude Messages API](https://docs.anthropic.com/en/api/messages)
- Mock API Documentation: See `../claude-mock-api/CLAUDE.md`

## Next Steps

1. ✅ **Simple agent created** — Basic Observe-Think-Act loop with Claude
2. **Add tools** — Give the agent capabilities (calculator, search, file ops)
3. **Implement memory** — Enable context retention across conversations
4. **Build multi-agent system** — Coordinate multiple agents
5. **Explore advanced patterns** — ReAct, Plan-and-Execute, tool chaining

---

**Note**: This is a learning project using Claude's native API format. Code examples prioritize clarity and educational value over production-grade optimization.
