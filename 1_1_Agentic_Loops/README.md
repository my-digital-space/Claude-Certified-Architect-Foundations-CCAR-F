# Simple AI Agent Example - Claude Native API

This is the first example in our journey to learn building AI agents with LangChain and Claude's native Anthropic API.

## What This Example Demonstrates

This script shows the **most basic form of an AI agent** using Claude:

1. **Receive input** — Get a question from the user
2. **Think** — Send the question to Claude LLM (via Anthropic Messages API) with system instructions
3. **Respond** — Return Claude's answer

### Key Concepts Covered

- **Claude LLM Configuration**: Connecting to our local mock API using `ChatAnthropic`
- **System Prompts**: Defining agent behavior and personality
- **Message Flow**: How messages are structured in Anthropic's Messages API
- **Basic Agent Loop**: The simplest form of an agentic system

### What This Agent CANNOT Do (Yet)

- ❌ Use tools (like calculators, web search, etc.)
- ❌ Remember previous conversations
- ❌ Access external data
- ❌ Take actions in the real world

These capabilities will be added in later examples!

## Prerequisites

1. **Mock API Server Running**
   ```bash
   cd ../claude-mock-api
   .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Virtual Environment Activated**
   ```bash
   .venv\Scripts\activate
   ```

3. **Dependencies Installed**
   ```bash
   pip install -r requirements.txt
   ```

## How to Run

### Option 1: Interactive Mode

Chat with the agent in real-time:

```bash
python 1_a_simple_AI_agent.py
```

Then choose option **1** for interactive chat.

Example interaction:
```
You: What is an AI agent?
[*] Agent is thinking (calling Claude API)...
Agent: An AI agent is a software program that uses artificial intelligence...
```

Type `quit` or `exit` to stop.

### Option 2: Example Queries Mode

Run predefined test queries:

```bash
python 1_a_simple_AI_agent.py
```

Then choose option **2** for example queries.

This will automatically run three test questions and show Claude's responses.

## Configuration

Customize the agent by editing the `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

Then edit `.env`:

```env
# Claude / Anthropic API Configuration (pointing to local mock API)
ANTHROPIC_API_URL=http://localhost:8000
ANTHROPIC_API_KEY=mock-api-key-001
MODEL_NAME=claude-3-5-sonnet-20241022
```

## Code Structure

The script is organized into clear steps:

1. **Imports** — Load required libraries (`langchain_anthropic`, `langchain_core`)
2. **LLM Configuration** — Set up `ChatAnthropic` connection to mock API
3. **System Prompt** — Define agent behavior
4. **SimpleAgent Class** — The agent implementation
5. **Interactive Demo** — Chat interface
6. **Example Queries** — Automated testing
7. **Main Entry Point** — Script execution

## Understanding the Code

### The Agent Loop (Claude Native API)

```python
def run(self, user_input: str) -> str:
    # 1. Create messages (system + user)
    messages = [
        SystemMessage(content=self.system_prompt),
        HumanMessage(content=user_input)
    ]
    
    # 2. Send to Claude via Anthropic Messages API
    response = self.llm.invoke(messages)
    
    # 3. Return response
    return response.content
```

This is the **core agentic loop** in its simplest form using Claude's native API.

### Why Use ChatAnthropic?

`ChatAnthropic` is LangChain's integration for Claude's native Anthropic API:

- **Native Format**: Uses `/v1/messages` endpoint (Anthropic's Messages API)
- **Better Integration**: Designed specifically for Claude's features
- **Future-Ready**: New Claude features come to the native API first
- **Cleaner API**: Separate `system` parameter vs embedded system messages

### Message Types

LangChain uses different message types:

- `SystemMessage` — Instructions for the AI (its "role" and behavior)
- `HumanMessage` — User input
- `AIMessage` — Agent responses (used in conversation history)

### API Request Format

When you call `llm.invoke()`, it sends to `POST /v1/messages`:

```json
{
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 1024,
  "system": "You are a helpful AI assistant...",
  "messages": [
    {"role": "user", "content": "What is an AI agent?"}
  ]
}
```

### API Response Format

Claude responds with:

```json
{
  "id": "msg_01XYZ...",
  "type": "message",
  "role": "assistant",
  "model": "claude-3-5-sonnet-20241022",
  "content": [
    {"type": "text", "text": "An AI agent is..."}
  ],
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 25,
    "output_tokens": 150
  }
}
```

## Troubleshooting

### "Error connecting to LLM"

**Solution**: Make sure the mock API server is running:

```bash
cd ../claude-mock-api
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Check server status:
```bash
curl http://localhost:8000/health
```

Should return: `{"status":"ok","version":"0.1.0"}`

### "Connection refused" or "Connection error"

The server might not be running. Start it as shown above.

### "Invalid API key"

Make sure your API key matches what's configured in the mock server's `.env` file.

Default is: `mock-api-key-001`

### Unicode/Encoding Errors on Windows

The script includes fallback handling for Unicode characters that Windows console can't display. If you see `?` characters, this is normal and doesn't affect functionality.

## Comparing OpenAI vs Claude API Styles

### Old Way (OpenAI Format)
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="mock-api-key-001",
    model="claude"
)
```

### New Way (Claude Native Format) ⭐
```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    anthropic_api_url="http://localhost:8000",
    anthropic_api_key="mock-api-key-001",
    model_name="claude-3-5-sonnet-20241022"
)
```

**Why the change?**
- More authentic learning experience
- Better Claude-specific feature support
- Cleaner API semantics
- Industry-standard Anthropic format

## Next Steps

After understanding this example, move on to:

1. **2_agent_with_tools.py** — Give the agent capabilities (calculator, search, etc.)
2. **3_agent_with_memory.py** — Enable conversation memory
3. **4_agent_with_context.py** — Advanced context management
4. **5_multi_agent_system.py** — Coordinate multiple agents

## Learning Exercise

Try modifying the agent:

1. **Change the system prompt** to make the agent respond differently (e.g., like a teacher, or very concise)
2. **Adjust temperature** (0.0 = consistent, 1.0 = creative) in `create_claude_llm()`
3. **Change max_tokens** to control response length
4. **Add more example queries** to test different scenarios
5. **Try different Claude models** by changing `MODEL_NAME` in `.env`

## Technical Notes

- **Model**: Uses Claude 3.5 Sonnet via local mock API (no API costs!)
- **Framework**: LangChain with Anthropic native integration
- **API Format**: Anthropic Messages API (`/v1/messages`)
- **Pattern**: Simple request-response (stateless)
- **Limitations**: No memory between calls, no tools, no context retention

## Switching to Production

When ready to use real Claude API:

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    # Remove anthropic_api_url -> uses https://api.anthropic.com
    anthropic_api_key="sk-ant-...",  # Real Anthropic API key
    model_name="claude-3-5-sonnet-20241022"
)
```

Get API keys at: https://console.anthropic.com/

---

**Remember**: This is a learning project! Experiment, break things, and learn from the results. The mock API lets you explore Claude's capabilities without costs or rate limits.
