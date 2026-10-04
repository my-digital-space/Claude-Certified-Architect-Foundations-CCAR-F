"""Wrapper around the Claude CLI (`claude --print`)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator

from app.config import settings

logger = logging.getLogger(__name__)


def format_messages_for_claude(
    messages: list[dict[str, Any]],
    explicit_system_prompt: str | None = None,
) -> tuple[str, str | None]:
    """Extract system prompt and compile conversation history into a unified prompt.

    Handles OpenAI/LangChain format:
    [
        {"role": "system", "content": "You are a coding assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"},
        {"role": "user", "content": "Write a python script"}
    ]
    """
    system_parts: list[str] = []
    if explicit_system_prompt:
        system_parts.append(explicit_system_prompt)

    dialogue_lines: list[str] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Handle multimodal/structured content blocks if provided
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            content = " ".join(text_parts)

        if role == "system":
            system_parts.append(str(content))
        elif role == "user":
            dialogue_lines.append(f"User: {content}")
        elif role == "assistant":
            dialogue_lines.append(f"Assistant: {content}")

    # If it's just a single user message, send it cleanly without "User:" prefix
    if len(dialogue_lines) == 1 and dialogue_lines[0].startswith("User: "):
        formatted_message = dialogue_lines[0][6:]
    else:
        formatted_message = "\n\n".join(dialogue_lines)

    combined_system = "\n\n".join(system_parts) if system_parts else None
    return formatted_message, combined_system


async def ask_claude(
    message: str,
    *,
    system_prompt: str | None = None,
    max_tokens: int | None = None,
    model: str = "claude",
) -> dict[str, Any]:
    """Run a blocking Claude CLI call and return an OpenAI-compatible completion response."""
    cmd = _build_command(message, system_prompt=system_prompt, max_tokens=max_tokens)
    logger.info("Invoking Claude CLI (blocking): %s", " ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    response_text = stdout.decode(errors="replace").strip()

    # Only treat as error if we got no response
    if not response_text:
        error_text = stderr.decode(errors="replace").strip()
        logger.error("Claude CLI failed (rc=%d): %s", proc.returncode, error_text)
        raise RuntimeError(f"Claude CLI error: {error_text}")

    # Log stderr warnings but don't fail
    if stderr:
        stderr_text = stderr.decode(errors="replace").strip()
        if stderr_text:
            logger.warning("Claude CLI stderr (non-fatal): %s", stderr_text[:200])

    logger.info("Claude CLI responded (%d chars)", len(response_text))

    created_time = int(time.time())
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created_time,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(message) // 4,
            "completion_tokens": len(response_text) // 4,
            "total_tokens": (len(message) + len(response_text)) // 4,
        },
    }


async def ask_claude_stream(
    message: str,
    *,
    system_prompt: str | None = None,
    max_tokens: int | None = None,
    model: str = "claude",
) -> AsyncIterator[str]:
    """Stream Claude CLI output chunk-by-chunk in standard OpenAI SSE chunk format."""
    cmd = _build_command(message, system_prompt=system_prompt, max_tokens=max_tokens)
    logger.info("Invoking Claude CLI (streaming): %s", " ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_time = int(time.time())

    # Send initial role chunk
    first_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": ""},
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(first_chunk)}\n\n"

    assert proc.stdout is not None  # for type-checker
    while True:
        chunk = await proc.stdout.read(256)
        if not chunk:
            break
        text = chunk.decode(errors="replace")
        event_data = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": text},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(event_data)}\n\n"

    # Send final chunk with finish_reason
    final_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"

    await proc.wait()
    if proc.returncode != 0:
        stderr_bytes = await proc.stderr.read() if proc.stderr else b""
        logger.error(
            "Claude CLI stream failed (rc=%d): %s",
            proc.returncode,
            stderr_bytes.decode(errors="replace"),
        )


async def ask_claude_messages(
    message: str,
    *,
    system_prompt: str | None = None,
    max_tokens: int | None = None,
    model: str = "claude-3-5-sonnet-20241022",
) -> dict[str, Any]:
    """Run Claude CLI and return a native Anthropic /v1/messages compatible response."""
    cmd = _build_command(message, system_prompt=system_prompt, max_tokens=max_tokens)
    logger.info("Invoking Claude CLI (Anthropic messages): %s", " ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    response_text = stdout.decode(errors="replace").strip()

    # Only treat as error if we got no response
    if not response_text:
        error_text = stderr.decode(errors="replace").strip()
        logger.error("Claude CLI failed (rc=%d): %s", proc.returncode, error_text)
        raise RuntimeError(f"Claude CLI error: {error_text}")

    # Log stderr warnings but don't fail
    if stderr:
        stderr_text = stderr.decode(errors="replace").strip()
        if stderr_text:
            logger.warning("Claude CLI stderr (non-fatal): %s", stderr_text[:200])

    logger.info("Claude CLI responded (%d chars)", len(response_text))

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [
            {
                "type": "text",
                "text": response_text,
            }
        ],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": max(1, len(message) // 4),
            "output_tokens": max(1, len(response_text) // 4),
        },
    }


async def ask_claude_messages_stream(
    message: str,
    *,
    system_prompt: str | None = None,
    max_tokens: int | None = None,
    model: str = "claude-3-5-sonnet-20241022",
) -> AsyncIterator[str]:
    """Stream Claude CLI output in native Anthropic SSE format."""
    cmd = _build_command(message, system_prompt=system_prompt, max_tokens=max_tokens)
    logger.info("Invoking Claude CLI (Anthropic streaming): %s", " ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    # Event 1: message_start
    start_event = {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {
                "input_tokens": max(1, len(message) // 4),
                "output_tokens": 1,
            },
        },
    }
    yield f"event: message_start\ndata: {json.dumps(start_event)}\n\n"

    # Event 2: content_block_start
    block_start_event = {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    }
    yield f"event: content_block_start\ndata: {json.dumps(block_start_event)}\n\n"

    total_output_chars = 0
    assert proc.stdout is not None
    while True:
        chunk = await proc.stdout.read(256)
        if not chunk:
            break
        text = chunk.decode(errors="replace")
        total_output_chars += len(text)
        delta_event = {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": text},
        }
        yield f"event: content_block_delta\ndata: {json.dumps(delta_event)}\n\n"

    # Event 3: content_block_stop
    block_stop_event = {
        "type": "content_block_stop",
        "index": 0,
    }
    yield f"event: content_block_stop\ndata: {json.dumps(block_stop_event)}\n\n"

    # Event 4: message_delta
    msg_delta_event = {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": max(1, total_output_chars // 4)},
    }
    yield f"event: message_delta\ndata: {json.dumps(msg_delta_event)}\n\n"

    # Event 5: message_stop
    msg_stop_event = {"type": "message_stop"}
    yield f"event: message_stop\ndata: {json.dumps(msg_stop_event)}\n\n"

    await proc.wait()


# ── helpers ──────────────────────────────────────────────────────────


def _build_command(
    message: str,
    *,
    system_prompt: str | None = None,
    max_tokens: int | None = None,
) -> list[str]:
    """Build the Claude CLI command list.

    Note: max_tokens parameter is kept for API compatibility but not used,
    as Claude CLI doesn't support --max-tokens flag.
    """
    cmd: list[str] = [settings.claude_cli_path, "--print"]

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    # Claude CLI doesn't support --max-tokens, so we skip it
    # The response length is controlled by Claude's default behavior

    cmd.extend(["--", message])
    return cmd
