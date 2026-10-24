"""
Step 6 — Add a safety iteration cap (MAX_ITERATIONS = 20) as a BACKSTOP, and log
a warning if it ever triggers.

The cap is a safety net, NOT the stopping mechanism. The real stop condition is
`stop_reason == "end_turn"`; a normal query terminates well before 20 iterations.
The cap only exists to stop a pathological runaway loop (e.g. a tool that keeps
giving Claude a reason to call another tool). If it fires, that's an anomaly — we
LOG A WARNING (not a silent stop, not a crash) so it's visible, then stop
gracefully.

EXAM TIP (this is the exact distinction the exam draws):
    - ACCEPTABLE: a cap as a fallback that should never trigger in normal use.
    - ANTI-PATTERN: using the cap as the PRIMARY control (looping a fixed N times,
      or relying on the counter instead of stop_reason to decide you're done).

Note: `main()` makes real (cheap) API calls on claude-haiku-4-5. The cap itself
is verified separately, offline, with a fake client (see the bottom of the file
and the project notes).
"""

# logging: the professional way to emit a warning (vs print). WARNING level is
# exactly right here — not an error (we stop gracefully), but louder than info
# because a triggered cap means something is wrong and a human should notice.
import logging

# json: pretty-print tool inputs while the loop runs.
import json

# ast + operator: evaluate the calculator expression safely (no eval()).
import ast
import operator

# dotenv: load the shared root .env (find_dotenv walks up from this subfolder).
from dotenv import load_dotenv, find_dotenv

# anthropic: the official SDK — client + Messages API.
import anthropic

load_dotenv(find_dotenv())

# Module-level logger. main() configures logging output; library-style code just
# grabs a named logger and logs to it.
logger = logging.getLogger(__name__)

# Default client. run_agent() accepts an override so tests can inject a fake one.
_default_client = anthropic.Anthropic()

MODEL = "claude-haiku-4-5"

# The safety cap. 20 is generous — real multi-tool chains in this project take a
# handful of iterations, so this should NEVER be reached in normal operation.
MAX_ITERATIONS = 20

# ---------------------------------------------------------------------------
# Tool definitions — carried over (each step file is self-contained).
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

# ---------------------------------------------------------------------------
# Tool implementations — carried over from Step 5.
# ---------------------------------------------------------------------------
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](
            _safe_eval(node.left), _safe_eval(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsupported or unsafe expression.")


def calculator(expression: str) -> str:
    # SECURITY: parse + walk an AST instead of eval() — tool input is untrusted.
    return str(_safe_eval(ast.parse(expression, mode="eval")))


_MOCK_SEARCH_DB = {
    "population of france": "The population of France is approximately 68000000 people.",
    "bitcoin": "The current price of Bitcoin is approximately 60000 USD.",
    "speed of light": "The speed of light is approximately 299792 kilometers per second.",
}


def web_search(query: str) -> str:
    q = query.lower()
    for keyword, fact in _MOCK_SEARCH_DB.items():
        if keyword in q:
            return fact
    return f"Mock results for '{query}': no specific data found."


def execute_tool(name: str, tool_input: dict) -> str:
    if name == "calculator":
        return calculator(tool_input["expression"])
    if name == "web_search":
        return web_search(tool_input["query"])
    raise ValueError(f"Unknown tool: {name}")


def extract_final_text(response) -> str:
    return "\n".join(b.text for b in response.content if b.type == "text")


def run_agent(user_prompt, client=None, max_iterations=MAX_ITERATIONS) -> dict:
    """Run the loop with a safety cap. Returns {answer, iterations, capped}.

    `client` and `max_iterations` are injectable so the cap can be tested with a
    fake client and a tiny cap (professional practice: dependency injection makes
    the backstop verifiable without 20 real API calls).
    """
    client = client or _default_client
    messages = [{"role": "user", "content": user_prompt}]

    # The explicit counter the exam asks for. We check it at the TOP of each
    # iteration, before doing any work.
    iterations = 0

    while True:
        # --- SAFETY BACKSTOP: check the counter FIRST ---
        # If we've hit the cap, something is wrong — a healthy run already exited
        # via `end_turn` below. Warn loudly and stop gracefully.
        if iterations >= max_iterations:
            # -> WARNING: Safety cap reached: 20 iterations without end_turn.
            # -> Stopping. (This should never happen in normal operation
            # -> - it signals a runaway loop, not a completed task.)
            logger.warning(
                "Safety cap reached: %d iterations without end_turn. "
                "Stopping. (This should never happen in normal operation - it "
                "signals a runaway loop, not a completed task.)",
                max_iterations,
            )
            return {
                "answer": "[stopped: hit MAX_ITERATIONS safety cap before end_turn]",
                "iterations": iterations,
                "capped": True,  # flag so callers can tell this was NOT a clean finish
            }

        iterations += 1
        print(f"\n=== Iteration {iterations} ===")  # -> === Iteration 1 ===

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=TOOLS,
            messages=messages,
        )
        print(f"stop_reason: {response.stop_reason}")  # -> stop_reason: tool_use

        # --- PRIMARY stop condition: stop_reason, not the counter ---
        if response.stop_reason == "end_turn":
            return {
                "answer": extract_final_text(response),
                "iterations": iterations,
                "capped": False,
            }

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    # -> Claude wants tool: web_search input: {"query": "population of France"}
                    print(f"Claude wants tool: {block.name} input: {json.dumps(block.input)}")
                    try:
                        result = execute_tool(block.name, block.input)
                        is_error = False
                    except Exception as exc:
                        result = f"Error: {exc}"
                        is_error = True
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        "is_error": is_error,
                    })
            messages.append({"role": "user", "content": tool_results})
            continue  # loop again — the counter guards against runaway

        # Other stop_reason (e.g. max_tokens): not a clean finish.
        return {
            "answer": f"[stopped: stop_reason={response.stop_reason}]",
            "iterations": iterations,
            "capped": False,
        }


def main():
    # Configure logging so the warning is visible if the cap ever fires.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    user_prompt = (
        "Search for the population of France, then calculate 15% of that number."
    )
    result = run_agent(user_prompt)

    print("\n----- Result -----")  # -> ----- Result -----
    print(f"iterations: {result['iterations']} capped: {result['capped']}")  # -> iterations: 3 capped: False
    # -> 15% of France's population (~68,000,000) is about 10,200,000.
    print(result["answer"])

    # In a healthy run, capped is False and iterations is small (~3) — proof the
    # cap is a backstop, not the thing that ended the loop.


if __name__ == "__main__":
    main()
