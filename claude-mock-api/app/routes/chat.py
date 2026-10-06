"""Chat completion routes supporting OpenAI-compatible and custom formats."""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.services.claude_cli import (
    ask_claude,
    ask_claude_messages,
    ask_claude_messages_stream,
    ask_claude_stream,
    format_messages_for_claude,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["chat"])


# ── Anthropic / Claude Messages API Models ───────────────────────────


class AnthropicMessage(BaseModel):
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: Any = Field(..., description="Message content (string or content block list)")


class AnthropicMessagesRequest(BaseModel):
    """Anthropic /v1/messages payload for ChatAnthropic / Anthropic Python SDK."""
    model: str = Field(default="claude-3-5-sonnet-20241022", description="Claude model name")
    messages: list[AnthropicMessage] = Field(..., min_length=1, description="Conversation messages")
    max_tokens: int = Field(default=4096, description="Max tokens to generate")
    system: str | list[dict[str, Any]] | None = Field(default=None, description="System prompt")
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    stream: bool = Field(default=False, description="Stream response via SSE")
    stop_sequences: list[str] | None = None
    tools: list[dict[str, Any]] | None = Field(default=None, description="Available tools for tool use")
    metadata: dict[str, Any] | None = None


# ── OpenAI-compatible Models ─────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: 'system', 'user', or 'assistant'")
    content: Any = Field(..., description="Message content (text or content parts)")


class ChatCompletionRequest(BaseModel):
    """OpenAI-standard payload for /v1/chat/completions (LangChain / LlamaIndex compatible)."""
    model: str = Field(default="claude", description="Model name (e.g. 'claude', 'gpt-4o')")
    messages: list[ChatMessage] = Field(..., min_length=1, description="List of messages")
    max_tokens: int | None = Field(None, gt=0, description="Max tokens in response")
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    stream: bool = Field(False, description="Stream response chunks via SSE")


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = int(time.time())
    owned_by: str = "claude-mock-api"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelCard]


# ── Legacy / Simple Request Format (Optional) ────────────────────────


class SimpleChatRequest(BaseModel):
    """Simplified single-message payload."""
    message: str = Field(..., min_length=1)
    system_prompt: str | None = None
    max_tokens: int | None = None
    stream: bool = False


# ── Routes ───────────────────────────────────────────────────────────


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    _api_key: Annotated[str, Depends(verify_api_key)],
) -> ModelListResponse:
    """List available models. Needed by LangChain / OpenAI SDKs."""
    now = int(time.time())
    return ModelListResponse(
        object="list",
        data=[
            ModelCard(id="claude", created=now),
            ModelCard(id="claude-3-5-sonnet", created=now),
            ModelCard(id="claude-3-opus", created=now),
            ModelCard(id="gpt-4o", created=now),
            ModelCard(id="gpt-3.5-turbo", created=now),
        ],
    )


@router.post("/chat/completions", response_model=None)
async def openai_chat_completions(
    body: ChatCompletionRequest,
    _api_key: Annotated[str, Depends(verify_api_key)],
) -> dict[str, Any] | StreamingResponse:
    """Standard OpenAI-compatible chat completion endpoint.

    Drop-in replacement for LangChain, LlamaIndex, OpenAI Python SDK, etc.
    """
    messages_dicts = [m.model_dump() for m in body.messages]
    formatted_msg, system_prompt = format_messages_for_claude(messages_dicts)
    max_tokens = body.max_tokens or settings.max_tokens

    if body.stream:
        return StreamingResponse(
            ask_claude_stream(
                formatted_msg,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                model=body.model,
            ),
            media_type="text/event-stream",
        )

    return await ask_claude(
        formatted_msg,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        model=body.model,
    )


@router.post("/chat", response_model=None)
async def simple_chat(
    body: SimpleChatRequest,
    _api_key: Annotated[str, Depends(verify_api_key)],
) -> dict[str, Any] | StreamingResponse:
    """Simple chat endpoint for direct single-message queries."""
    max_tokens = body.max_tokens or settings.max_tokens

    if body.stream:
        return StreamingResponse(
            ask_claude_stream(
                body.message,
                system_prompt=body.system_prompt,
                max_tokens=max_tokens,
            ),
            media_type="text/event-stream",
        )

    return await ask_claude(
        body.message,
        system_prompt=body.system_prompt,
        max_tokens=max_tokens,
    )


@router.post("/messages", response_model=None)
async def anthropic_messages(
    body: AnthropicMessagesRequest,
    _api_key: Annotated[str, Depends(verify_api_key)],
) -> dict[str, Any] | StreamingResponse:
    """Native Anthropic Messages API endpoint.

    Compatible with:
    - langchain-anthropic (ChatAnthropic)
    - anthropic Python SDK
    - Direct Anthropic API clients

    Request format:
    {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "system": "You are a helpful assistant.",
        "stream": false
    }
    """
    # Extract system prompt
    system_prompt = None
    if body.system:
        if isinstance(body.system, str):
            system_prompt = body.system
        elif isinstance(body.system, list):
            # System can be a list of text blocks
            system_parts = [
                block.get("text", "")
                for block in body.system
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            system_prompt = "\n\n".join(system_parts) if system_parts else None

    # Format messages for Claude CLI
    messages_dicts = [m.model_dump() for m in body.messages]
    formatted_msg, extracted_system = format_messages_for_claude(
        messages_dicts, explicit_system_prompt=system_prompt
    )

    # Use the combined system prompt
    final_system = extracted_system

    if body.stream:
        return StreamingResponse(
            ask_claude_messages_stream(
                formatted_msg,
                system_prompt=final_system,
                max_tokens=body.max_tokens,
                model=body.model,
            ),
            media_type="text/event-stream",
        )

    return await ask_claude_messages(
        formatted_msg,
        system_prompt=final_system,
        max_tokens=body.max_tokens,
        model=body.model,
        tools=body.tools,
        messages=messages_dicts,
    )
