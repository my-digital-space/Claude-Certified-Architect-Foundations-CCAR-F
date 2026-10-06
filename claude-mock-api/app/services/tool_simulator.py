"""Tool-use simulation engine for the Anthropic Messages API agentic loop.

This module lets the mock server behave like a real Anthropic endpoint that
supports tool calling, WITHOUT calling a real LLM. It is intentionally
deterministic and easy to read so it doubles as a teaching tool for agentic
loops.

How the loop works (mirrors what a real Anthropic API does):

    Turn 1   user: "What's the weather in Paris?"
             assistant: [tool_use get_weather]   stop_reason=tool_use

    Turn 2   user: [tool_result <...>]          # client executed the tool
             assistant: [tool_use get_time]     stop_reason=tool_use   (if more
                                                           relevant tools remain)
                  ... or ...
             assistant: [text "..."]            stop_reason=end_turn   (when done)

Control-flow rule (deterministic, generic, no hard-coded business logic):

    * Scan the assistant history for ``tool_use`` blocks and record which tool
      names have already been called.
    * Look at the *original* user question (first real user message) to decide
      which of the remaining tools are relevant.
    * If a relevant tool has not been called yet -> return a ``tool_use`` block
      for it (``stop_reason="tool_use"``).
    * Otherwise (no remaining relevant tool) -> return a final text answer built
      from the collected ``tool_result`` blocks (``stop_reason="end_turn"``).

This guarantees the client can observe a full
``request -> tool_use -> tool_result -> request -> tool_use -> ... -> end_turn``
loop, supports multiple sequential iterations where later calls follow earlier
results, and terminates cleanly for any set of tools the client supplies.

Argument extraction keeps the synthetic tool calls *plausible*:

    * String parameters are filled from the question text: quoted phrases,
      place names for place-like parameters, or the word in the "of a X" /
      "for a X" slot that best matches the parameter name. The whole question
      is never dumped into a single argument.
    * Numeric parameters prefer an explicit number in the question; otherwise
      the most recent earlier ``tool_result`` value is fed in. This models
      dependent tools, e.g. ``apply_discount(base_price=<price tool result>)``.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# English function/question words to ignore when extracting proper nouns
# (locations, names, ...) from a user query.
_STOPWORDS = frozenset(
    {
        "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
        "is", "are", "was", "were", "the", "a", "an", "and", "or", "but",
        "this", "that", "these", "in", "on", "at", "to", "for",
        "of", "with", "about", "please", "tell", "get", "show", "find",
        "current", "today", "now", "what's", "can", "could", "would", "you",
    }
)


class ToolUseSimulator:
    """Deterministic tool selection & response synthesis for agentic loops."""

    def __init__(self, tools: list[dict[str, Any]] | None = None) -> None:
        """Initialize with the tool definitions from the request.

        Args:
            tools: Anthropic-format tool definitions, e.g.::

                [{
                    "name": "get_weather",
                    "description": "Get the weather for a location",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City"}
                        },
                        "required": ["location"]
                    }
                }]
        """
        self.tools = tools or []
        self.tool_map: dict[str, dict[str, Any]] = {t.get("name"): t for t in self.tools}

    # ── conversation analysis ────────────────────────────────────────

    def _tools_called_so_far(self, messages: list[dict[str, Any]]) -> set[str]:
        """Return the set of tool names already present in assistant tool_use blocks."""
        called: set[str] = set()
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        name = block.get("name")
                        if name:
                            called.add(name)
        return called

    def _remaining_tools(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Tools that have not been called yet, preserving client-provided order."""
        called = self._tools_called_so_far(messages)
        return [t for t in self.tools if t.get("name") not in called]

    def _original_user_query(self, messages: list[dict[str, Any]]) -> str:
        """Return the text of the FIRST real user message (the actual task).

        Using the first user message (rather than the latest) keeps relevance
        stable across turns: on later turns the most recent user message is a
        ``tool_result`` wrapper, not the original question.
        """
        for msg in messages:
            if msg.get("role") != "user":
                continue
            text = self._text_of_content(msg.get("content"))
            if text.strip():
                return text.strip()
        return ""

    @staticmethod
    def _text_of_content(content: Any) -> str:
        """Extract plain text from an Anthropic message content value."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return " ".join(parts)
        return ""

    # ── decision: tool_use vs end_turn ───────────────────────────────

    def should_use_tools(self, messages: list[dict[str, Any]]) -> bool:
        """Return True if a tool_use response should be produced now.

        True when at least one *relevant* tool has not been called yet. On a
        fresh conversation (no tool activity so far) we also return True so the
        loop reliably starts, even if keyword relevance is marginal.
        """
        if not self.tools:
            return False

        remaining = self._remaining_tools(messages)
        if not remaining:
            return False

        query = self._original_user_query(messages)
        relevant = [t for t in remaining if self._is_relevant(t, query)]

        # If a remaining tool clearly matches the task -> definitely call one.
        if relevant:
            return True

        # No clearly-relevant tool left, but this is the very first turn (no
        # tool has been called yet). Start the loop by using a tool anyway.
        called = self._tools_called_so_far(messages)
        if not called:
            logger.info("🔧 Fresh task with tools available; starting agentic loop")
            return True

        # We've already made tool calls and nothing else is relevant -> finish.
        logger.info("✅ No remaining relevant tools; will produce final answer (end_turn)")
        return False

    # ── which tool to call, and with what args ───────────────────────

    def select_tools_to_call(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build the single tool_use block to return this turn.

        Exactly one tool is called per turn so the client sees a clear
        iteration. The most relevant un-called tool is chosen; if none is
        clearly relevant the first un-called tool is used as a fallback.
        """
        remaining = self._remaining_tools(messages)
        if not remaining:
            return []

        query = self._original_user_query(messages)
        relevant = [t for t in remaining if self._is_relevant(t, query)]
        chosen = relevant[0] if relevant else remaining[0]

        tool_input = self._generate_tool_input(chosen, query, messages)
        tool_use_block = {
            "type": "tool_use",
            "id": f"toolu_{uuid.uuid4().hex[:20]}",
            "name": chosen.get("name", "unknown"),
            "input": tool_input,
        }

        logger.info(
            "🛠️  Calling tool '%s' with args %s",
            chosen.get("name"),
            json.dumps(tool_input)[:200],
        )
        return [tool_use_block]

    def _is_relevant(self, tool: dict[str, Any], query: str) -> bool:
        """Heuristic: does this tool seem applicable to the user's task?"""
        if not query:
            return False
        q = query.lower()
        name = (tool.get("name") or "").lower().replace("_", " ")
        desc = (tool.get("description") or "").lower()

        if name in q:
            return True
        if tool.get("name") and tool["name"].lower() in q:
            return True

        # Match a couple of distinctive words from the description.
        for word in re.findall(r"[a-z]{4,}", desc):
            if word in q:
                return True
        return False

    def _generate_tool_input(
        self,
        tool: dict[str, Any],
        query: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Produce JSON-compatible arguments that match the tool's input_schema."""
        schema = tool.get("input_schema") or {}
        properties = schema.get("properties") or {}
        required = schema.get("required") or []

        tool_input: dict[str, Any] = {}
        for prop_name, prop_schema in properties.items():
            if not isinstance(prop_schema, dict):
                continue
            prop_type = prop_schema.get("type", "string")
            prop_desc = prop_schema.get("description", "")
            value = self._extract_value(
                query, prop_name, prop_type, prop_desc, messages
            )

            # Always fill required params (fall back to a sensible default).
            if prop_name in required or value is not None:
                tool_input[prop_name] = value

        return tool_input

    def _extract_value(
        self,
        query: str,
        param_name: str,
        param_type: str,
        param_desc: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Best-effort extraction of a parameter value from the user's question."""
        q_lower = query.lower()

        if param_type == "string":
            # 1) Quoted text
            quoted = re.findall(r'["\']([^"\']+)["\']', query)
            if quoted:
                return quoted[0]
            # 2) A proper noun / location-ish phrase.
            #    Skip English function/question words so "What is the weather
            #    in Paris?" yields "Paris", not "What". A capitalized word
            #    introduced by a place preposition ("in California") wins.
            if any(k in param_name.lower() for k in ("location", "city", "place", "state")):
                words = query.split()
                filtered = [w for w in words if w[:1].isupper() and w.lower() not in _STOPWORDS]
                for j, w in enumerate(words):
                    if w in filtered and j > 0 and words[j - 1].lower() in ("in", "to", "from", "at"):
                        return w
                if filtered:
                    return filtered[0]
                cap = re.findall(r"\b[A-Z][a-zA-Z]+\b", query)
                if cap:
                    return cap[-1]
            # 3) Words that follow the parameter name in the question
            token = param_name.replace("_", " ")
            if token in q_lower:
                after = q_lower.split(token, 1)[1].strip().split()[:3]
                if after:
                    return " ".join(after)
            # 4) A concrete entity word from the "of a X" / "for a X" slot
            #    (covers product_name, customer_type, ...) that best matches
            #    the parameter name.
            entity = self._entity_word(query, param_name, param_desc)
            if entity:
                return entity
            # 5) Parameter name as a placeholder — never the whole question.
            return param_name

        if param_type in ("integer", "number"):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", query)
            if nums:
                return int(nums[0]) if param_type == "integer" else float(nums[0])
            # Dependent tools: feed the most recent earlier tool_result into
            # this numeric parameter (e.g. base_price = price tool's output).
            if messages:
                results = self._collect_tool_results(messages)
                if results:
                    last = results[-1]
                    m = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*", str(last[1]))
                    if m:
                        return float(m.group(1)) if param_type == "number" else int(float(m.group(1)))
            return 0

        if param_type == "boolean":
            return any(w in q_lower for w in ("yes", "true", "enable", "on"))

        if param_type == "array":
            item = self._extract_value(query, param_name, "string", param_desc, messages)
            return [item]

        return None

    def _entity_word(self, query: str, param_name: str, param_desc: str) -> str | None:
        """Pick the most likely concrete entity word for a string parameter.

        Strategy: find words sitting in an "of a X" / "for a X" slot in the
        question, then prefer the one that best matches the parameter name
        (word-stem equality, containment either way, or noun-overlap with the
        description). Falls back to the first such word.

        Example: "What is the final price of a laptop for a Gold customer
        in California?" -> candidates are {laptop, gold, customer,
        california}; for ``product_name`` the best match is "laptop".
        """
        words = re.findall(r"\b[a-zA-Z]+\b", query.lower())

        # Candidate slots: "of a laptop" -> laptop, "for a gold customer" -> gold
        slots: list[int] = []  # word indices
        for i in range(len(words) - 2):
            if words[i] in ("of", "for") and words[i + 1] in ("a", "an"):
                slots.append(i + 2)

        fallback = [i for i, w in enumerate(words) if w not in _STOPWORDS]
        if not slots and not fallback:
            return None

        candidates = slots if slots else fallback

        stem = param_name.replace("_", "")
        param_parts = [p for p in param_name.lower().split("_") if len(p) >= 4]
        desc_words = set(re.findall(r"[a-z]+", param_desc.lower()))

        def score(idx: int) -> int:
            word = words[idx]
            s = word.replace("s", "")  # crude plural-insensitive stem
            # 4) Adjective-before-noun: "for a gold customer" -> customer_type
            #    picks "gold" because the following word matches a param part.
            if idx + 1 < len(words):
                if any(part in words[idx + 1] for part in param_parts):
                    return 4
            if s == stem:
                return 3
            if stem in s or s in stem:
                return 2
            if any(noun[:4] in s or s[:4] in noun for noun in desc_words):
                return 1
            return 0

        best = max(candidates, key=score)
        if score(best) == 0:
            # No word matches the parameter name; fall back to the first
            # "of a X" entity — the question's main subject (e.g. "laptop").
            if slots:
                best = slots[0]
            else:
                return None
        # Preserve the original capitalization from the question.
        m = re.search(rf"\b{re.escape(words[best])}\b", query, re.IGNORECASE)
        return m.group(0) if m else words[best]

    # ── synthesizing the final answer ────────────────────────────────

    def synthesize_final_response(self, messages: list[dict[str, Any]]) -> str:
        """Build a final, human-readable answer from the collected tool_results."""
        original = self._original_user_query(messages)

        results = self._collect_tool_results(messages)

        if not results:
            # No tools were actually run; give a simple, honest answer.
            return "I processed your request."

        lines = [f"Here is the result for your question: \"{original}\"."]
        for i, (name, value) in enumerate(results, start=1):
            pretty = self._prettify(value)
            lines.append(f"\n{i}. Tool '{name}' returned:\n{pretty}")
        lines.append("\nBased on the above, the request has been completed.")
        return "\n".join(lines)

    def _collect_tool_results(
        self,
        messages: list[dict[str, Any]],
    ) -> list[tuple[str, str]]:
        """Gather (tool_name, result_text) pairs from user tool_result blocks.

        Anthropic tool_result blocks carry a ``tool_use_id`` but not the tool
        name, so we match results back to tools by the order of tool_use blocks
        in the assistant turn that preceded them.
        """
        # Map tool_use_id -> tool name from assistant turns.
        id_to_name: dict[str, str] = {}
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        id_to_name[block.get("id", "")] = block.get("name", "unknown")

        out: list[tuple[str, str]] = []
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    name = id_to_name.get(block.get("tool_use_id", ""), "tool")
                    raw = block.get("content", "")
                    if isinstance(raw, list):
                        text_parts = [
                            p.get("text", "") if isinstance(p, dict) else str(p)
                            for p in raw
                        ]
                        raw = " ".join(text_parts)
                    out.append((name, raw if isinstance(raw, str) else json.dumps(raw)))
        return out

    @staticmethod
    def _prettify(value: str) -> str:
        """Try to pretty-print a JSON-ish result string; fall back to raw text."""
        try:
            parsed = json.loads(value)
            return json.dumps(parsed, indent=2)
        except (json.JSONDecodeError, TypeError):
            return value
