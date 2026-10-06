"""End-to-end tests for the simulated Anthropic tool-use agentic loop.

These tests drive the /v1/messages endpoint the way a LangChain ChatAnthropic
client would across multiple iterations:

    task -> tool_use -> (client runs tool) -> tool_result -> tool_use -> ...
    -> end_turn

They use the built-in FastAPI TestClient, so no real Claude CLI is required.
"""

from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

API_KEY = settings.mock_api_key
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# A realistic set of tools that a learning agent might expose.
WEATHER_TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a given city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Name of the city"}
            },
            "required": ["city"],
        },
    },
    {
        "name": "get_timezone",
        "description": "Get the timezone offset for a given city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Name of the city"}
            },
            "required": ["city"],
        },
    },
]


def post_messages(payload: dict) -> dict:
    """POST /v1/messages and return the parsed JSON response."""
    resp = client.post("/v1/messages", json=payload, headers=HEADERS)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_first_turn_returns_tool_use():
    """A fresh task with available tools must come back as stop_reason=tool_use."""
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "tools": WEATHER_TOOLS,
        "messages": [
            {"role": "user", "content": "What is the weather in Paris?"}
        ],
    }
    result = post_messages(payload)

    # Anthropic response shape
    assert result["type"] == "message"
    assert result["role"] == "assistant"
    assert result["stop_reason"] == "tool_use"
    assert result["stop_sequence"] is None

    # First content block is a tool_use with a valid id + name + input
    block = result["content"][0]
    assert block["type"] == "tool_use"
    assert block["id"].startswith("toolu_")
    assert block["name"] in {t["name"] for t in WEATHER_TOOLS}
    assert isinstance(block["input"], dict)
    # The required 'city' argument must be present and match the request
    assert block["input"].get("city") == "Paris"


def test_multi_tool_loop_then_end_turn():
    """Drive a full loop: call both tools across turns, then terminate."""
    original_query = "What is the weather in Paris and what timezone is it?"
    messages: list[dict] = [{"role": "user", "content": original_query}]
    payloads = {"tools": WEATHER_TOOLS, "model": "claude-3-5-sonnet-20241022", "max_tokens": 512}

    called_names: list[str] = []
    for _ in range(5):  # safety bound
        resp = post_messages({**payloads, "messages": copy.deepcopy(messages)})

        if resp["stop_reason"] == "tool_use":
            # Extract the assistant tool_use block(s) and append to history.
            assistant_content = [b for b in resp["content"] if b["type"] == "tool_use"]
            messages.append({"role": "assistant", "content": assistant_content})
            called_names.extend(b["name"] for b in assistant_content)

            # Simulate the client executing the tool and returning a result.
            tool_results = [
                {
                    "type": "tool_result",
                    "tool_use_id": b["id"],
                    "content": f"<result from {b['name']}>",
                }
                for b in assistant_content
            ]
            messages.append({"role": "user", "content": tool_results})
            continue

        # end_turn reached -> this is the final answer
        assert resp["stop_reason"] == "end_turn"
        assert any(b["type"] == "text" for b in resp["content"])
        text = next(b["text"] for b in resp["content"] if b["type"] == "text")
        assert "Paris" in text or "timezone" in text.lower()
        break
    else:
        raise AssertionError("Agentic loop did not terminate within 5 turns")

    # Both relevant tools should have been exercised across the loop.
    assert "get_weather" in called_names
    assert "get_timezone" in called_names


def test_tool_result_without_more_tools_ends():
    """After the single relevant tool is used, the next turn must end_turn."""
    messages: list[dict] = [
        {"role": "user", "content": "What is the weather in London?"}
    ]
    # Turn 1: tool_use
    r1 = post_messages(
        {"tools": WEATHER_TOOLS, "messages": messages, "max_tokens": 512}
    )
    assert r1["stop_reason"] == "tool_use"
    block = r1["content"][0]
    assert block["name"] == "get_weather"
    assert block["input"].get("city") == "London"

    # Build the follow-up request exactly as the client would.
    messages.append({"role": "assistant", "content": [block]})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": [{"type": "text", "text": "Sunny, 22C"}],
                }
            ],
        }
    )
    # Turn 2: no more relevant tools -> end_turn with a synthesized answer.
    r2 = post_messages(
        {"tools": WEATHER_TOOLS, "messages": messages, "max_tokens": 512}
    )
    assert r2["stop_reason"] == "end_turn"
    text = next(b["text"] for b in r2["content"] if b["type"] == "text")
    assert "Sunny, 22C" in text


def test_no_tools_still_returns_end_turn():
    """Without tools the endpoint behaves like a plain completion (end_turn)."""
    resp = post_messages(
        {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Say hello."}],
            "tool": None,  # no tools key
        }
    )
    assert resp["stop_reason"] == "end_turn"
    assert resp["type"] == "message"
    assert any(b["type"] == "text" for b in resp["content"])


def test_anthropic_style_x_api_key_auth():
    """Auth must also work via the Anthropic x-api-key header."""
    resp = client.post(
        "/v1/messages",
        json={
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 256,
            "tools": WEATHER_TOOLS,
            "messages": [{"role": "user", "content": "Weather in Tokyo?"}],
        },
        headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stop_reason"] == "tool_use"
