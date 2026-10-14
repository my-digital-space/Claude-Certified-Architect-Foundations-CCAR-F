""" 
Step 1 — Set up a Claude API client and register two tools. 

Goal of this step: define a *multi-tool* surface so that, in later steps, Claude 
has to make a model-driven decision about WHICH tool fits the user's request. 
That decision-making is the heart of an agentic architecture — we're building the 
menu now; the loop that acts on Claude's choices comes in later steps. 

What you should see when you run this: 
 - Two tool definitions, each a valid Anthropic tool: name, description, and an 
 input_schema that is a JSON Schema object (type / properties / required). 
 - A client that is ready to talk to the Messages API. 

We do NOT call the API yet. This step is purely about defining the tools 
correctly — run it to confirm the schemas are well-formed. 
"""

# json: used only to pretty-print the tool schemas so we can eyeball that each 
# input_schema is valid, well-formed JSON Schema. 
import json

# dotenv: reads the shared .env file and injects its values (notably 
# ANTHROPIC_API_KEY) into the process environment, so we don't hardcode secrets. 
# - find_dotenv walks UP the directory tree from this file until it finds .env. 
# We need it because this step lives in a project subfolder ("1.1 Agentic 
# Loops/") while the shared .env sits at the repo root one level up. This 
# works no matter which directory you run the script from. 
from dotenv import load_dotenv, find_dotenv

# anthropic: the official Anthropic SDK — provides the client we use to talk to 
# the Claude Messages API and the tool-definition shapes it expects. 
import anthropic

# Load .env BEFORE constructing the client, so ANTHROPIC_API_KEY is in the 
# environment by the time the SDK looks for it. (Step 1 doesn't call the API, but 
# we keep the pattern consistent across every step file.) 
load_dotenv(find_dotenv())

# The client reads ANTHROPIC_API_KEY from the environment. Never hardcode a key. 
client = anthropic.Anthropic()

# Low-cost model — this is practice only. 
MODEL = "claude-haiku-4-5"

# --------------------------------------------------------------------------- 
# Tool definitions. 
# 
# Every Anthropic tool needs exactly three things: 
# - name: a short identifier Claude uses to pick the tool 
# - description: natural-language text Claude reads to decide WHEN to use it 
# (be specific — this is what drives correct tool selection) 
# - input_schema: a JSON Schema OBJECT describing the arguments. It must have 
# "type": "object", a "properties" map, and a "required" list. 
# 
# These are the same three fields in any language's SDK — only the syntax 
# differs. Here they are Python dicts that serialize to the JSON the API wants. 
# 
# EXAM TIP: The field is `input_schema` (snake_case) and its value is JSON 
# Schema. Remember the trio name / description / input_schema — the exam likes 
# to swap in wrong names (e.g. "parameters", "schema") as distractors. 
# EXAM TIP: Claude selects a tool purely from its `name` and `description`. A 
# vague description is the usual cause of "Claude picked the wrong tool" — the 
# fix is a clearer description, not more code. 
# --------------------------------------------------------------------------- 

TOOLS = [
    {
        # Tool 1: a calculator. Takes a single math expression string.
        "name": "calculator",
        "description": (
            "Evaluates a mathematical expression and returns the numeric result. "
            "Use this whenever the user asks for arithmetic or a calculation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                # One argument: the expression to evaluate, as a string.
                "expression": {
                    "type": "string",
                    "description": "The math expression, e.g. '2 + 3 * 4'.",
                },
            },
            "required": ["expression"],  # Claude must supply an expression.
        },
    },
    {
        # Tool 2: a web search STUB. Same shape as a real tool, but in a later
        # step its implementation will just return mock results — enough for
        # Claude to have a genuinely different tool to choose between.
        "name": "web_search",
        "description": (
            "Searches the web for up-to-date information and returns results. "
            "Use this when the user asks about current events, facts, or anything "
            "that is not a pure calculation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                # One argument: the search query, as a string.
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
    # No API call yet — just prove the tools are registered and well-formed.
    print(f"Client ready. Model: {MODEL}")  # -> Client ready. Model: claude-haiku-4-5
    print(f"Registered {len(TOOLS)} tool(s):\n")  # -> Registered 2 tool(s):
    for tool in TOOLS:
        # -> - calculator: Evaluates a mathematical expression and returns ...
        print(f"- {tool['name']}: {tool['description']}")
        # Pretty-print the schema so we can eyeball that it's valid JSON Schema.
        # -> {
        # -> "type": "object",
        # -> "properties": {"expression": {"type": "string", "description": "..."}},
        # -> "required": ["expression"]
        # -> }
        print(json.dumps(tool["input_schema"], indent=2))
        print()  # -> (blank separator line)


if __name__ == "__main__":
    main()
