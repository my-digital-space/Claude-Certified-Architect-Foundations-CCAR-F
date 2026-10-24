"""
Step 2 — The agentic loop: call Claude, then inspect `stop_reason`.

Goal of this step: establish the core execution pattern of an agent — a loop
that calls the Messages API and, after EACH response, looks at
`response.stop_reason` to decide what to do next.

Why `stop_reason` specifically:
    `stop_reason` is the API's deterministic, authoritative signal for loop
    control. It is the ONE correct way to know whether Claude wants to keep
    working (`"tool_use"`) or is finished (`"end_turn"`).
    Do NOT drive the loop by inspecting `content[0].type`, counting turns, or
    parsing Claude's natural-language text — those are unreliable proxies.

What you should see when you run this:
    - A `for` loop that calls `client.messages.create(...)`.
    - After each call, a printed `stop_reason`, and a branch on its value.
    - We break on `"end_turn"`. If we see `"tool_use"`, we print the tool Claude
      chose and stop for now — actually EXECUTING the tool and feeding the result
      back (so the loop can genuinely continue) is Step 3.

Note: this makes a real (cheap) API call on claude-haiku-4-5.
"""

# json: to pretty-print the tool-use input Claude returns, so we can see the
# arguments it chose.
import json

# dotenv: reads the shared .env file and injects its values (notably
# ANTHROPIC_API_KEY) into the process environment, so we don't hardcode secrets.
# - find_dotenv walks UP the directory tree from this file until it finds .env.
# We need it because this step lives in a project subfolder ("1.1 Agentic
# Loops/") while the shared .env sits at the repo root one level up. This
# works no matter which directory you run the script from.
from dotenv import load_dotenv, find_dotenv

# anthropic: the official SDK — gives us the client and the Messages API.
import anthropic

# Load .env BEFORE constructing the client, so ANTHROPIC_API_KEY is in the
# environment by the time the SDK looks for it.
load_dotenv(find_dotenv())

# The client reads ANTHROPIC_API_KEY from the environment. Never hardcode a key.
client = anthropic.Anthropic()

# Low-cost model — practice only.
MODEL = "claude-haiku-4-5"

# ---------------------------------------------------------------------------
# Tools — carried over verbatim from Step 1 (each step file is self-contained,
# so duplicating this block is intentional).
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "calculator",
        "description": (
            "Evaluates a mathematical expression and returns the numeric result. "
            "Use this whenever the user asks for arithmetic or a calculation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The math expression, e.g. '2 + 3 * 4'.",
                },
            },
            "required": ["expression"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Searches the web for up-to-date information and returns results. "
            "Use this when the user asks about current events, facts, or anything "
            "that is not a pure calculation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query text.",
                },
            },
            "required": ["query"],
        },
    },
]


def main():
    # A prompt that should make Claude reach for the calculator tool, so we can
    # observe stop_reason == "tool_use" on the first iteration.
    user_prompt = "What is 15 * 23?"

    # Conversation history. The API is stateless — we resend the full history on
    # every call. It starts with just the user's message.
    #
    # EXAM TIP: "The Messages API is stateless" is a favorite exam point. The
    # server keeps NO memory between requests; the `messages` list you send IS
    # the entire context. Lose it and Claude forgets everything.
    messages = [{"role": "user", "content": user_prompt}]

    # Safety backstop ONLY. The real stop condition is stop_reason == "end_turn";
    # this cap just prevents an accidental infinite loop while we build up the
    # logic. See CLAUDE.md on appropriate vs inappropriate use of the cap.
    MAX_ITERATIONS = 10

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n=== Iteration {iteration} ===")  # -> === Iteration 1 ===

        # Send the whole conversation plus the available tools.
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=TOOLS,
            messages=messages,
        )

        # THE key line: stop_reason is the authoritative loop-control signal.
        #
        # EXAM TIP: This is THE core idea of the agentic loop. Control the loop
        # with `stop_reason` — a deterministic field the API sets. Distractor
        # answers tell you to check `content[0].type`, scan Claude's text for
        # "I'm done", or count turns. Those are unreliable; `stop_reason` is the
        # single correct, deterministic signal.
        print(f"stop_reason: {response.stop_reason}")  # -> stop_reason: tool_use

        if response.stop_reason == "end_turn":
            # Claude finished naturally. Print its final text and exit cleanly.
            for block in response.content:
                if block.type == "text":
                    print(f"Final answer: {block.text}")  # -> Final answer: 15 * 23 = 345
            break

        if response.stop_reason == "tool_use":
            # Claude wants to call one or more tools. In this step we only
            # OBSERVE that decision — we show which tool(s) it picked and with
            # what arguments. Executing them and appending results (so the loop
            # can continue past this point) is Step 3.
            for block in response.content:
                if block.type == "tool_use":
                    print(f"Claude wants tool: {block.name}")  # -> Claude wants tool: calculator
                    print(f"  input: {json.dumps(block.input)}")  # -> input: {"expression": "15 * 23"}
            # -> (Tool execution + result feedback comes in Step 3 - stopping here.)
            print("(Tool execution + result feedback comes in Step 3 - stopping here.)")
            break

        # Any other stop_reason (e.g. max_tokens) is not a clean finish; surface
        # it rather than looping blindly.
        #
        # EXAM TIP: Know the common stop_reason values: "end_turn" (done),
        # "tool_use" (wants a tool), "max_tokens" (hit the output cap —
        # truncated, NOT finished), and "stop_sequence". "max_tokens" means the
        # answer was cut off; the fix is a larger max_tokens, not treating it
        # as a completed turn.
        # -> Unhandled stop_reason: max_tokens - stopping.
        print(f"Unhandled stop_reason: {response.stop_reason} - stopping.")
        break
    else:
        # The for/else runs only if the loop exhausted the cap without breaking —
        # i.e. we never hit end_turn. That's an anomaly worth surfacing.
        # -> Stopped: hit MAX_ITERATIONS safety cap before end_turn.
        print("Stopped: hit MAX_ITERATIONS safety cap before end_turn.")


if __name__ == "__main__":
    main()
