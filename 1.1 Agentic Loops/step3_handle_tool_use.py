""" 
Step 3 — Handle the `tool_use` stop reason: run the tool, return the result, 
and let the loop continue. 

This is the critical handoff in an agentic loop. When Claude stops with 
`stop_reason == "tool_use"`, we must: 
 1. Append Claude's FULL response as the assistant turn (text + tool_use blocks). 
 2. Execute each requested tool. 
 3. Send the result(s) back as a `tool_result`, inside ONE user message. 
 4. NOT break — fall through so the loop calls the API again. Claude reads the 
 result and continues, eventually finishing with `stop_reason == "end_turn"`. 

Compared to Step 2, the `tool_use` branch no longer stops the loop — that single 
change is what turns "observe once" into a real multi-turn agent. 

Note: this makes real (cheap) API calls on claude-haiku-4-5. 
""" 

# json: to pretty-print tool inputs for visibility while the loop runs. 
import json 

# ast + operator: used to evaluate the calculator expression SAFELY. See the 
# security note on calculator() below for why we do NOT use eval(). 
import ast 
import operator 

# dotenv: load the shared root .env (find_dotenv walks up from this subfolder). 
from dotenv import load_dotenv, find_dotenv 

# anthropic: the official SDK — client + Messages API. 
import anthropic 

# Load .env before constructing the client so ANTHROPIC_API_KEY is available. 
load_dotenv(find_dotenv()) 

client = anthropic.Anthropic() 

# Low-cost model — practice only. 
MODEL = "claude-haiku-4-5" 

# --------------------------------------------------------------------------- 
# Tool definitions — carried over from Step 1 (each step file is self-contained). 
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
# Tool IMPLEMENTATIONS. 
# 
# A tool definition (above) only tells Claude the tool EXISTS and its schema. 
# The actual work happens here, on our side. Claude never runs code — it only 
# asks us to; WE execute and hand back the result. 
# --------------------------------------------------------------------------- 

# Operators we allow the calculator to use. Mapping AST node types -> functions. 
_ALLOWED_OPERATORS = { 
 ast.Add: operator.add, 
 ast.Sub: operator.sub, 
 ast.Mult: operator.mul, 
 ast.Div: operator.truediv, 
 ast.Pow: operator.pow, 
 ast.Mod: operator.mod, 
 ast.USub: operator.neg, # unary minus, e.g. -5 
 ast.UAdd: operator.pos, # unary plus, e.g. +5 
} 

def _safe_eval(node): 
 """Recursively evaluate a parsed arithmetic expression, allowing ONLY 
 numbers and the operators in _ALLOWED_OPERATORS.""" 
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
 # Anything else (function calls, names, attributes, ...) is rejected. 
 raise ValueError("Unsupported or unsafe expression.") 

def calculator(expression: str) -> str: 
 """Evaluate a math expression and return the result as a string. 

 GOTCHA / SECURITY: never do `eval(expression)` on text that came from a 
 model or a user — eval runs ARBITRARY Python (file deletes, network calls, 
 etc.). We parse to an AST and walk only numbers + arithmetic operators, so 
 nothing dangerous can execute. Tool inputs are untrusted input — treat them 
 that way. 
 """ 
 tree = ast.parse(expression, mode="eval") 
 return str(_safe_eval(tree)) 

def web_search(query: str) -> str: 
 """STUB: return fixed, fake results so the agent has a second, genuinely 
 different tool to choose. A real implementation would call a search API.""" 
 return ( 
 f"Mock results for '{query}':\n" 
 "1. Example result A — https://example.com/a\n" 
 "2. Example result B — https://example.com/b" 
 ) 

def execute_tool(name: str, tool_input: dict) -> str: 
 """Dispatch a tool call by name to the matching Python function. 

 `tool_input` is already a decoded dict — the SDK parsed Claude's JSON for us. 
 EXAM TIP: read values out of the dict (tool_input["expression"]); do NOT 
 string-match the raw/serialized JSON. 
 """ 
 if name == "calculator": 
 return calculator(tool_input["expression"]) 
 if name == "web_search": 
 return web_search(tool_input["query"]) 
 # Unknown tool name — surface it as an error string (handled as is_error below). 
 raise ValueError(f"Unknown tool: {name}") 

def main(): 
 user_prompt = "What is 15 * 23? Then tell me what the latest Mars rover is." 

 # Stateless API: we resend the whole history every call. Start with the user. 
 messages = [{"role": "user", "content": user_prompt}] 

 # Safety backstop ONLY — not the stop condition. The clean exit is end_turn. 
 MAX_ITERATIONS = 10 

 for iteration in range(1, MAX_ITERATIONS + 1): 
 print(f"\n=== Iteration {iteration} ===") # -> === Iteration 1 === 

 response = client.messages.create( 
 model=MODEL, 
 max_tokens=4096, 
 tools=TOOLS, 
 messages=messages, 
 ) 

 # stop_reason is the authoritative loop-control signal. 
 print(f"stop_reason: {response.stop_reason}") # -> stop_reason: tool_use 

 if response.stop_reason == "end_turn": 
 # Claude is done. Print its final text and exit cleanly. 
 for block in response.content: 
 if block.type == "text": 
 # -> Final answer: 
 # -> 15 * 23 = 345. The latest Mars rover is Perseverance. 
 print(f"\nFinal answer:\n{block.text}") 
 break 

 if response.stop_reason == "tool_use": 
 # --- THE HANDOFF (the heart of Step 3) --- 

 # (1) Append Claude's FULL response as the assistant turn. 
 # EXAM TIP: append the entire `response.content`, not just the text. 
 # It contains the tool_use block(s); the API needs them present so 
 # it can match our tool_result(s) back to them. Appending only the 
 # text would drop the tool_use blocks and the next call would 400. 
 messages.append({"role": "assistant", "content": response.content}) 

 # (2) Execute EVERY tool_use block in this response. 
 # GOTCHA: one assistant turn can contain MULTIPLE tool_use blocks 
 # (parallel tool use). The JS starter used .find() and ran only the 
 # first — that silently drops the rest. We loop over all of them. 
 tool_results = [] 
 for block in response.content: 
 if block.type == "tool_use": 
 print(f"Claude wants tool: {block.name}") # -> Claude wants tool: calculator 
 print(f" input: {json.dumps(block.input)}") # -> input: {"expression": "15 * 23"} 

 # Run the tool; on failure return is_error instead of crashing. 
 try: 
 result = execute_tool(block.name, block.input) 
 is_error = False 
 except Exception as exc: 
 result = f"Error: {exc}" 
 is_error = True 

 # (3) Build one tool_result per tool_use. 
 # EXAM TIP: tool_use_id MUST match the id of the tool_use 
 # block it answers — this is how the API pairs them. 
 tool_results.append({ 
 "type": "tool_result", 
 "tool_use_id": block.id, 
 "content": result, 
 "is_error": is_error, 
 }) 

 # (4) Send ALL tool results back in a SINGLE user message. 
 # EXAM TIP: all results from one assistant turn go in ONE user 
 # message — not one message per result. 
 messages.append({"role": "user", "content": tool_results}) 

 # (5) NO break. Fall through -> the for loop iterates -> we call the 
 # API again with the results in history, and Claude continues. 
 continue 

 # Any other stop_reason (e.g. max_tokens = truncated) is not a clean 
 # finish; surface it rather than looping blindly. 
 # -> Unhandled stop_reason: max_tokens - stopping. 
 print(f"Unhandled stop_reason: {response.stop_reason} - stopping.") 
 break 
 else: 
 # Ran out of iterations without ever hitting end_turn — the backstop 
 # fired. In a healthy run this never prints. 
 # -> Stopped: hit MAX_ITERATIONS safety cap before end_turn. 
 print("Stopped: hit MAX_ITERATIONS safety cap before end_turn.") 

if __name__ == "__main__": 
 main() 