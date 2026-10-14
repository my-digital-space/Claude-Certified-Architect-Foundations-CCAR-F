# CLAUDE.md 

Guidance for Claude Code when working in this repository. 

## How this file is organized 

This file grows over time, so it is split into two kinds of content: 

- **Shared conventions** (the sections immediately below) apply to **every** 
 project in the repo: layout, golden rules, environment/secrets, and the 
 default Claude API conventions. 
- **Per-project sections** come after, one `## Project: X.Y Name` heading each. 
 A project section is self-contained: its overview, learning objectives, 
 reference notes, exam tips, and a step-by-step log. When a new project starts, 
 add a new `## Project:` section — don't bloat the shared part. 

Projects so far: 
- [Project: 1.1 Agentic Loops](#project-11-agentic-loops) — code-complete. 

--- 

# Shared conventions (all projects) 

## Repository layout 

This repo holds **many small step-by-step projects**. Shared tooling lives at the 
root and is reused by every project; each project gets its own subfolder. 

``` 
Claude_certification/ 
├─ .venv/ # shared virtual environment (all projects use it) 
├─ .env # shared secrets (git-ignored) ← real ANTHROPIC_API_KEY 
├─ .env.example # committed template 
├─ .gitignore 
├─ requirements.txt # pinned Python dependencies (shared) 
├─ README.md # human quickstart 
├─ CLAUDE.md # this file — shared conventions + per-project sections 
└─ 1.1 Agentic Loops/ # one project = one folder 
 ├─ step1_tools.py 
 ├─ step2_agentic_loop.py 
 ├─ step3_handle_tool_use.py 
 ├─ step4_return_final_response.py 
 ├─ step5_sequential_tools.py 
 └─ step6_safety_cap.py 
``` 

- **Shared at root:** venv, `.env`, `requirements.txt`, `README.md`, `CLAUDE.md`, 
 `.gitignore`. Don't duplicate these per project. 
- **Dependencies:** when you `pip install` a new package, add it (pinned, with a 
 why-comment) to `requirements.txt`. Keep it to direct deps only. 
- **Per project:** a numbered/named folder (e.g. `1.1 Agentic Loops/`) holding 
 that project's `step<N>_*.py` files. 
- Step files load the shared root `.env` with `load_dotenv(find_dotenv())` — 
 `find_dotenv` walks up from the step file to the root, so it works from any 
 subfolder depth and regardless of the current working directory. 

## Golden rules 

- **Python only — always.** Generate all code in Python, no matter what the user 
 pastes. If a sample is pasted in JavaScript, TypeScript, Go, cURL, or any other 
 language, treat it as a *reference for intent* and translate it into idiomatic 
 Python using the `anthropic` SDK. Never emit code in another language. 
- **Comment the code.** Every generated file includes clear code comments that 
 explain *what* each part does and *why* — enough that the learning objective is 
 visible from reading the source alone. Favor comments on the API-shape and 
 loop-control decisions (tool schemas, `stop_reason` handling, appending 
 history). 
- **Comment every import.** Each `import` line gets a short comment saying *why* 
 that module is needed in this file (not just what it is). 
- **One file per step.** Each step is its own self-contained `step<N>_*.py` file. 
 Duplicating code carried over from an earlier step is fine and expected — each 
 file should run on its own without importing from the others, so a step reads 
 top-to-bottom as a complete example. 
- **Professional practices (Anthropic style).** Write the code the way Anthropic's 
 own examples do: construct the client with a bare `anthropic.Anthropic()` and 
 let it read the key from the environment; never hardcode secrets; use the SDK's 
 typed objects and helpers rather than re-parsing raw JSON; parse `block.input` 
 as already-decoded data (never string-match the serialized tool input); return 
 a `tool_result` with `is_error: True` on tool failures instead of crashing; 
 prefer clear names and small functions. Keep it readable over clever. 
- **ASCII-only console/log output (Windows).** The Windows console isn't UTF-8 by 
 default, so non-ASCII characters (em-dashes `—`, smart quotes, emoji) in 
 `print`/`logging` output render as mojibake (`�`). Keep runtime output ASCII 
 (use `-`, `'`, `"`). Non-ASCII is fine inside `.md` files and comments. 
- **Show a sample of every output.** For each `print()` / `logging` / other 
 output statement, add a short inline comment showing a *mock* example of what 
 that line might print, so the reader knows what to expect without running the 
 code. It need not be exact — a representative sample is enough. Use a 
 `# ->` prefix, e.g.: 

 ```python 
 print(f"stop_reason: {response.stop_reason}") # -> stop_reason: tool_use 
 print(f"Total iterations: {result['iterations']}") # -> Total iterations: 3 
 ``` 
- **Beginner framing + exam tips.** The user is new to this and is preparing for 
 the **Claude Certified Architect — Foundations** exam. Explain concepts plainly 
 in comments, and flag exam-relevant points inline with a `# EXAM TIP:` or 
 `# GOTCHA:` prefix so they're easy to scan. Put them where the concept lives in 
 the code. 
- **Build incrementally.** One concept per step. Do not jump ahead to the full 
 solution — add the smallest piece that teaches the next objective, run it, then 
 continue. 
- **Verify offline when possible.** Prefer proving logic without spending API 
 calls: `py_compile` for syntax, unit-test pure functions directly, and inject a 
 fake client to exercise loop/termination behavior. Only the end-to-end run 
 needs a real key. 

## Environment 

Python virtual environment. **Always activate the venv before running anything** 
(python, pip, any step script). 

Windows — this machine's shells: 

```powershell 
# PowerShell (primary) 
python -m venv .venv # once, to create it 
.\.venv\Scripts\Activate.ps1 # activate — do this first, every session 
pip install -r requirements.txt 
``` 

```bash 
# Git Bash (Bash tool) 
python -m venv .venv # once 
source .venv/Scripts/activate # activate — do this first, every session 
pip install -r requirements.txt 
``` 

### Secrets via `.env` 

The key lives in a local `.env` file, loaded by `python-dotenv`. Every step file 
calls `load_dotenv(find_dotenv())` **before** constructing the client. 

- `.env` — real secrets; **git-ignored**, never committed. Ships with a dummy 
 placeholder key that must be replaced with a real `sk-ant-...` key before any 
 API-calling step. 
- `.env.example` — safe, committed template; copy to `.env` and fill in. 
- `.gitignore` — excludes `.env`, `.venv/`, and `__pycache__/`. 

```python 
from dotenv import load_dotenv, find_dotenv # why: read root .env into env 
load_dotenv(find_dotenv()) # call before anthropic.Anthropic() 
``` 

Alternatively, set it directly for one session instead of using `.env`: 

```powershell 
$env:ANTHROPIC_API_KEY = "sk-ant-..." # PowerShell, current session 
``` 

## Shared Claude API conventions (authoritative — do not guess) 

- **Model:** `claude-haiku-4-5` — low-cost ($1/$5 per 1M tokens), this is 
 practice only. Use the exact ID string, no date suffix. (If a step ever needs 
 more capability, step up to `claude-sonnet-5`; default stays Haiku.) 
- **Client:** `client = anthropic.Anthropic()` (picks up `ANTHROPIC_API_KEY`). 
- **`max_tokens`:** `4096` is plenty for these exercises. Haiku 4.5 caps at 64K 
 output and has a 200K context window. 
- **Thinking:** omit it. (Haiku 4.5 is an older-family model — adaptive thinking / 
 `effort` are not supported on it, so leave `thinking` unset.) 
- **Tool definitions** use `name`, `description`, `input_schema` (JSON Schema). 
- **Parse `block.input` as already-decoded data**; never raw-string-match the 
 serialized tool input. 

--- 

# Project: 1.1 Agentic Loops 

Build a **Multi-Tool Agent Loop from scratch, step by step**, against the Claude 
Messages API — one working Python program grown incrementally, explaining each 
addition before writing it. **Status: code-complete** (all six steps); only an 
end-to-end run with a real key remains to see it live. 

## Learning objectives 

1. How the agentic loop lifecycle works with the Messages API. 
2. Why `stop_reason` is the authoritative signal for loop control. 
3. How to handle the `tool_use` and `end_turn` stop reasons correctly. 
4. How to append tool results to conversation history for multi-turn execution. 
5. When safety iteration caps are appropriate versus inappropriate as a stopping 
 mechanism. 

## Reference: stop reasons & the loop 

| `stop_reason` | Meaning | Loop action | 
| --- | --- | --- | 
| `tool_use` | Claude wants to call a tool | execute tool(s), append results, continue | 
| `end_turn` | Claude finished naturally | **stop** (extract + return the text) | 
| `max_tokens`| Hit the output cap | truncated — not a clean finish | 

The manual loop shape this project builds up to: 

```python 
client = anthropic.Anthropic() 
messages = [{"role": "user", "content": user_input}] 

MAX_ITERATIONS = 20 # safety backstop ONLY — not the stop condition 
iterations = 0 
while True: 
 if iterations >= MAX_ITERATIONS: # check the backstop first 
 logger.warning("Safety cap reached ...") # warn, don't crash/silently stop 
 break 
 iterations += 1 

 response = client.messages.create( 
 model="claude-haiku-4-5", max_tokens=4096, tools=TOOLS, messages=messages, 
 ) 

 if response.stop_reason == "end_turn": # PRIMARY stop condition 
 return "\n".join(b.text for b in response.content if b.type == "text") 

 if response.stop_reason == "tool_use": 
 messages.append({"role": "assistant", "content": response.content}) # FULL turn 
 tool_results = [] 
 for block in response.content: 
 if block.type == "tool_use": 
 try: 
 result = execute_tool(block.name, block.input) # input is decoded 
 is_error = False 
 except Exception as e: 
 result, is_error = f"Error: {e}", True # don't crash 
 tool_results.append({ 
 "type": "tool_result", 
 "tool_use_id": block.id, # MUST match the tool_use id 
 "content": result, 
 "is_error": is_error, 
 }) 
 messages.append({"role": "user", "content": tool_results}) # ALL results, ONE msg 
 continue # no break -> continues 
``` 

### Safety iteration cap — appropriate vs inappropriate 

- **Appropriate:** a backstop that prevents an infinite loop if a tool keeps 
 feeding Claude reasons to call more tools. When it fires, that's an anomaly — 
 log/surface it, don't swallow it. A healthy run never reaches it. 
- **Inappropriate:** using the cap as the normal way to end the loop, or setting 
 it so low it truncates legitimate multi-step work. The clean exit is always 
 `stop_reason == "end_turn"`. 

## Exam cheat-sheet (Claude Certified Architect — Foundations) 

High-value facts this project demonstrates — the kind of thing the exam probes. 

- **`stop_reason` is the authoritative loop signal.** Loop while `tool_use`, 
 stop on `end_turn`. Never branch on `content[0].type`, never parse Claude's 
 prose, never use a turn counter as the real stop condition. 
- **The Messages API is stateless.** You resend the *entire* conversation history 
 on every call. The API remembers nothing between requests. 
- **Append the full `response.content`** (every block — text *and* `tool_use`) to 
 history as the assistant turn before sending results. Appending only the text 
 loses the `tool_use` blocks and breaks the next request. 
- **`tool_result` must echo the matching `tool_use_id`.** Mismatched/missing IDs 
 are an error. 
- **All tool_results from one assistant turn go back in a single `user` 
 message** — not one message per result. 
- **One assistant turn can hold multiple `tool_use` blocks** (parallel tool use) — 
 execute them all; don't process only the first. 
- **A tool's `description` drives selection.** Claude picks tools from their 
 `name`/`description`, so write them clearly and specifically. 
- **`input_schema` is JSON Schema** with `type: "object"`, `properties`, and 
 `required`. 
- **Failed tool → `tool_result` with `is_error: True`**, not an exception that 
 kills the loop. Claude can read the error and recover. 
- **Sequential/chained tool calls are just more loop iterations** — no special 
 API feature; each is one request/response round-trip. 
- **Final answer lives in `type == "text"` content blocks** — join all of them, 
 don't take only the first. 
- **Safety iteration cap = backstop, not stop condition.** Appropriate to prevent 
 runaway loops; inappropriate as the normal way to end. A clean run ends on 
 `end_turn`. 
- **Parse `block.input` as data** (the SDK already decoded it) — don't 
 string-match serialized JSON. 

## Step log 

- **Env:** `.venv` + `anthropic` (1.13.0) + `python-dotenv` (1.2.4) installed; 
 `.env` wired via `load_dotenv(find_dotenv())`. Objective: reusable scaffolding. 
- **Step 1 — tool definitions.** [step1_tools.py](1.1%20Agentic%20Loops/step1_tools.py) 
 — client + two tools (`calculator`, `web_search` stub) with valid JSON Schema 
 `input_schema`. Teaches the `name`/`description`/`input_schema` trio and that 
 `description` drives selection. Verified by running it (prints both schemas; no 
 API call). 
- **Step 2 — the loop + `stop_reason`.** [step2_agentic_loop.py](1.1%20Agentic%20Loops/step2_agentic_loop.py) 
 — a loop that calls the API and branches on `stop_reason` (the authoritative 
 signal). Observes the `tool_use` block only, then stops (execution is Step 3). 
 Teaches stateless history + `stop_reason` control. Needs a real key to run. 
- **Step 3 — the tool handoff.** [step3_handle_tool_use.py](1.1%20Agentic%20Loops/step3_handle_tool_use.py) 
 — on `tool_use`: append the full assistant turn, execute every `tool_use` block 
 (safe AST calculator; `eval()` rejected for security), return all `tool_result`s 
 in one user message with matching `tool_use_id`, then `continue` (no break) so 
 the loop proceeds to `end_turn`. Tool functions + unsafe-expression rejection 
 unit-tested offline. 
- **Step 4 — return the final answer.** [step4_return_final_response.py](1.1%20Agentic%20Loops/step4_return_final_response.py) 
 — refactored into `run_agent(prompt) -> str`; on `end_turn`, `extract_final_text` 
 joins ALL `type=="text"` blocks (not just the first) and RETURNS the answer. 
 `extract_final_text` unit-tested offline. 
- **Step 5 — sequential (chained) tools.** [step5_sequential_tools.py](1.1%20Agentic%20Loops/step5_sequential_tools.py) 
 — prompt that forces search → calculate-on-the-result. `web_search` stub gained 
 a canned, number-bearing knowledge base so the chain is real; `run_agent` 
 returns `{answer, iterations, tool_calls}` to verify >=2 tool iterations before 
 `end_turn`. Chain math verified offline. 
- **Step 6 — safety cap backstop.** [step6_safety_cap.py](1.1%20Agentic%20Loops/step6_safety_cap.py) 
 — `MAX_ITERATIONS = 20` with an explicit counter checked at the top of each 
 loop; on hit, logs a WARNING via `logging` and stops gracefully with 
 `capped: True`. `run_agent` made injectable (`client`/`max_iterations`), which 
 let the cap be *proven* to fire offline via a fake runaway client (no API 
 calls). Teaches backstop-vs-primary-control. 

**Done next time:** run any API-calling step end-to-end with a real key in `.env` 
(e.g. `python "1.1 Agentic Loops/step5_sequential_tools.py"`) to watch the live 
loop; observe iterations stay well under the cap. 