"""Tests for OpenAI compatibility, LangChain integration, and API features."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

API_KEY = settings.mock_api_key


# ── Health ───────────────────────────────────────────────────────────


def test_health_check() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Auth ─────────────────────────────────────────────────────────────


def test_chat_without_key_returns_401() -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


def test_chat_with_wrong_key_returns_403() -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 403


# ── OpenAI / LangChain Compatibility ─────────────────────────────────


def test_models_endpoint() -> None:
    resp = client.get("/v1/models", headers={"Authorization": f"Bearer {API_KEY}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 1
    model_ids = [m["id"] for m in data["data"]]
    assert "claude" in model_ids


@patch("app.routes.chat.ask_claude", new_callable=AsyncMock)
def test_openai_chat_completions(mock_ask: AsyncMock) -> None:
    mock_ask.return_value = {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from mock!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ],
    }

    resp = client.post(
        "/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "Hello from mock!"
    mock_ask.assert_awaited_once()


# ── Simple Chat ───────────────────────────────────────────────────────


@patch("app.routes.chat.ask_claude", new_callable=AsyncMock)
def test_simple_chat_blocking(mock_ask: AsyncMock) -> None:
    mock_ask.return_value = {
        "id": "chatcmpl-test456",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "claude",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
    }

    resp = client.post(
        "/v1/chat",
        json={"message": "Hello, Claude!"},
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "Hello!"
    mock_ask.assert_awaited_once()


# ── Key Rotation ──────────────────────────────────────────────────────


def test_rotate_key() -> None:
    original_key = settings.mock_api_key

    resp = client.post(
        "/admin/rotate-key",
        headers={"Authorization": f"Bearer {original_key}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    new_key = data["new_api_key"]
    assert new_key != original_key
    assert new_key.startswith("mock-")

    # Old key should now be rejected
    resp2 = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": f"Bearer {original_key}"},
    )
    assert resp2.status_code == 403

    # Restore original key
    settings.mock_api_key = original_key
