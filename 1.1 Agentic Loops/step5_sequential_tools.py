""" 
Step 5 — Sequential (chained) tool calls: search first, then calculate using 
the search result, and verify the loop runs through MULTIPLE iterations before 
`end_turn`. 

This exercises the FULL loop lifecycle. A single prompt forces a dependency 
chain: 
 iteration 1: Claude calls web_search -> we return a number 
 iteration 2: Claude calls calculator on it -> we return the product 
 iteration 3: Claude has everything -> end_turn (final answer) 

The loop code did not change from Step 4 — that's the point. Because we 
`continue` after every `tool_use` instead of breaking, chaining "just works": 
each tool result goes back into history, Claude reasons about it, and decides 
whether it needs another tool. The agent, not our code, drives the sequence. 

One setup detail: `web_search` is a STUB. For the chain to be meaningful it must 
return a usable NUMBER, so below it has a tiny canned "knowledge base". A real 
search tool would return real data; the loop mechanics are identical. 

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
# Tool implementations. 
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

# A tiny fake "web" so the search stub can return a NUMBER the calculator can 
# then use. Keyed by a substring we look for in the query. This is the only 
# change from the Step 4 stub, and it exists purely to make the chain testable. 
_MOCK_SEARCH_DB = { 
 "population of france": "The population of France is approximately 68000000 people.", 
 "bitcoin": "The current price of Bitcoin is approximately 60000 USD.", 
 "speed of light": "The speed of light is approximately 299792 kilometers per second.", 
} 

def web_search(query: str) -> str: 
 """STUB search. Returns a canned fact (containing a number) when the query 
 matches a known topic, otherwise a generic 'nothing found' message.""" 
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
 """Join all text blocks of a finished response (see Step 4).""" 
 return "\n".join(b.text for b in response.content if b.type == "text") 

def run_agent(user_prompt: str) -> dict: 
 """Run the loop and return a small result dict so we can VERIFY the chain: 
 {"answer": str, "iterations": int, "tool_calls": [ (iteration, name), ... ]} 

 EXAM TIP: "sequential tool calls" just means the loop runs several times. 
 Each iteration is one full request/response round-trip. There is no special 
 API feature for chaining — the agent calls a tool, reads the result, and on 
 the NEXT iteration decides whether it needs another one. Our job is only to 
 keep feeding results back and not break early. 
 """ 
 messages = [{"role": "user", "content": user_prompt}] 
 MAX_ITERATIONS = 10 

 tool_calls = [] # record (iteration, tool_name) to prove the sequence 

 for iteration in range(1, MAX_ITERATIONS + 1): 
 print(f"\n=== Iteration {iteration} ===") # -> === Iteration 1 === 

 response = client.messages.create( 
 model=MODEL, 
 max_tokens=4096, 
 tools=TOOLS, 
 messages=messages, 
 ) 
 print(f"stop_reason: {response.stop_reason}") # -> stop_reason: tool_use (then tool_use, then end_turn) 

 if response.stop_reason == "end_turn": 
 return { 
 "answer": extract_final_text(response), 
 "iterations": iteration, 
 "tool_calls": tool_calls, 
 } 

 if response.stop_reason == "tool_use": 
 messages.append({"role": "assistant", "content": response.content}) 

 tool_results = [] 
 for block in response.content: 
 if block.type == "tool_use": 
 tool_calls.append((iteration, block.name)) # log the call 
 print(f"Claude wants tool: {block.name}") # -> Claude wants tool: web_search 
 print(f" input: {json.dumps(block.input)}") # -> input: {"query": "population of France"} 
 try: 
 result = execute_tool(block.name, block.input) 
 is_error = False 
 except Exception as exc: 
 result = f"Error: {exc}" 
 is_error = True 
 print(f" -> result: {result}") # -> -> result: The population of France is approximately 68000000 people. 
 tool_results.append({ 
 "type": "tool_result", 
 "tool_use_id": block.id, 
 "content": result, 
 "is_error": is_error, 
 }) 

 messages.append({"role": "user", "content": tool_results}) 
 continue 

 return { 
 "answer": f"[stopped: stop_reason={response.stop_reason}]", 
 "iterations": iteration, 
 "tool_calls": tool_calls, 
 } 

 return { 
 "answer": "[stopped: hit MAX_ITERATIONS safety cap before end_turn]", 
 "iterations": MAX_ITERATIONS, 
 "tool_calls": tool_calls, 
 } 

def main(): 
 # This prompt FORCES a chain: the calculation needs the search result as its 
 # input, so Claude cannot answer in one shot — it must search, then compute. 
 user_prompt = ( 
 "Search for the population of France, then calculate 15% of that number." 
 ) 

 result = run_agent(user_prompt) 

 # Verification summary — this is what Step 5 asks us to observe. 
 print("\n----- Verification -----") # -> ----- Verification ----- 
 print(f"Total iterations: {result['iterations']}") # -> Total iterations: 3 
 print("Tool call sequence:") # -> Tool call sequence: 
 for iteration, name in result["tool_calls"]: 
 # -> iteration 1: web_search 
 # -> iteration 2: calculator 
 print(f" iteration {iteration}: {name}") 
 # We expect at least two tool calls (web_search then calculator) before end_turn. 
 distinct_tools = {name for _, name in result["tool_calls"]} 
 print(f"Distinct tools used: {sorted(distinct_tools)}") # -> Distinct tools used: ['calculator', 'web_search'] 
 print("\n----- Final answer -----") # -> ----- Final answer ----- 
 # -> 15% of France's population (~68,000,000) is about 10,200,000. 
 print(result["answer"]) 

if __name__ == "__main__": 
 main() 