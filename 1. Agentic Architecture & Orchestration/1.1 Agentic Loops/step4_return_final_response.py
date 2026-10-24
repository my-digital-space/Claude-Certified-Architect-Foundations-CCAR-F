"""
Step 4 — Handle the `end_turn` stop reason: extract Claude's final text and
RETURN it, closing the loop.

`end_turn` is Claude's signal that the task is complete. Steps 2-3 only *printed*
when this happened; here we do the real job of a loop — pull the final
user-facing text out of the response and `return` it, so the agent becomes a
reusable function that hands an answer back to its caller.

The whole agent now lives in `run_agent(user_prompt) -> str`:
    - loop: call API, branch on stop_reason
    - tool_use -> run tools, append results, continue (from Step 3)
    - end_turn -> extract text, RETURN it (the focus of this step)

Note: this makes real (cheap) API calls on claude-haiku-4-5.
"""

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

client = anthropic.Anthropic()

MODEL = "claude-haiku-4-5"

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
# Tool implementations — carried over from Step 3.
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


def web_search(query: str) -> str:
    return (
        f"Mock results for '{query}':\n"
        "1. Example result A — https://example.com/a\n"
        "2. Example result B — https://example.com/b"
    )


def execute_tool(name: str, tool_input: dict) -> str:
    if name == "calculator":
        return calculator(tool_input["expression"])
    if name == "web_search":
        return web_search(tool_input["query"])
    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Extracting the final answer (the focus of Step 4).
# ---------------------------------------------------------------------------
def extract_final_text(response) -> str:
    """Pull Claude's user-facing text out of a finished (end_turn) response.

    EXAM TIP: the final answer lives in the response's content blocks whose
    `type == "text"`. (tool_use blocks are instructions to US, not the user.)

    GOTCHA: the JS starter used `.find()` — it returns only the FIRST text block.
    A response can legitimately contain MULTIPLE text blocks (e.g. text around
    a tool call). Join them all so nothing is dropped.
    """
    parts = [block.text for block in response.content if block.type == "text"]
    return "\n".join(parts)


def run_agent(user_prompt: str) -> str:
    """Run the full agentic loop and RETURN Claude's final answer as a string."""
    # Stateless API: resend full history each call. Start with the user message.
    messages = [{"role": "user", "content": user_prompt}]

    # Safety backstop ONLY — the clean exit is end_turn, handled below.
    MAX_ITERATIONS = 10

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n=== Iteration {iteration} ===")  # -> === Iteration 1 ===

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=TOOLS,
            messages=messages,
        )

        print(f"stop_reason: {response.stop_reason}")  # -> stop_reason: tool_use

        if response.stop_reason == "end_turn":
            # Task complete. Extract the final text and RETURN it — this is what
            # closes the loop and hands the result back to the caller. Returning
            # (not printing) is what makes run_agent reusable: a web handler, a
            # test, or another function can consume the answer.
            return extract_final_text(response)

        if response.stop_reason == "tool_use":
            # The handoff from Step 3 (unchanged): append assistant turn, run all
            # tools, return results in one user message, continue the loop.
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"Claude wants tool: {block.name}")  # -> Claude wants tool: calculator
                    print(f"  input: {json.dumps(block.input)}")  # -> input: {"expression": "15 * 23"}
                    try:
                        result = execute_tool(block.name, block.input)
                        is_error = False
                    except Exception as exc:
                        result = f"Error: {exc}"
                        is_error = True
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,  # must match the tool_use id
                        "content": result,
                        "is_error": is_error,
                    })

            messages.append({"role": "user", "content": tool_results})
            continue

        # Not a clean finish (e.g. max_tokens = truncated). Return what we can,
        # labeled, rather than pretending it was a normal end_turn.
        return f"[stopped: stop_reason={response.stop_reason}] " + extract_final_text(response)

    # Fell out of the loop via the safety cap without an end_turn. Surface it as
    # the returned value instead of silently returning "".
    return "[stopped: hit MAX_ITERATIONS safety cap before end_turn]"


def main():
    user_prompt = "What is 15 * 23? Then tell me what the latest Mars rover is."

    # run_agent RETURNS the answer; main() decides what to do with it (here: print).
    answer = run_agent(user_prompt)
    print("\n----- Returned answer -----")  # -> ----- Returned answer -----
    # -> 15 * 23 = 345. The latest Mars rover is Perseverance.
    print(answer)


if __name__ == "__main__":
    main()
