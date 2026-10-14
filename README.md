# Claude Certification — Practice Projects 

A collection of small, step-by-step projects for learning to build on the Claude 
API, as preparation for the **Claude Certified Architect — Foundations** exam. 

Shared tooling (virtual environment, secrets, dependencies) lives at the repo 
root and is reused by every project. Each project is its own numbered folder. 

## Layout 

``` 
Claude_certification/ 
├─ .venv/ # shared virtual environment 
├─ .env # shared secrets (git-ignored) — your real API key 
├─ .env.example # template to copy to .env 
├─ requirements.txt # pinned Python dependencies 
├─ README.md # this file (human quickstart) 
├─ CLAUDE.md # conventions + exam notes used while building 
└─ 1.1 Agentic Loops/ # project 1: build a multi-tool agent loop 
 ├─ step1_tools.py 
 └─ step2_agentic_loop.py 
``` 

## Setup (one time) 

```bash 
# 1. Create the virtual environment 
python -m venv .venv 

# 2. Activate it 
.\.venv\Scripts\Activate.ps1 # PowerShell 
source .venv/Scripts/activate # Git Bash 

# 3. Install dependencies 
pip install -r requirements.txt 

# 4. Create your .env and add your real key 
cp .env.example .env # Git Bash (PowerShell: Copy-Item .env.example .env) 
# then edit .env and set ANTHROPIC_API_KEY=sk-ant-... 
``` 

Get an API key from the [Anthropic Console](https://console.anthropic.com/). 

## Running a step 

Activate the venv first (every session), then run any step file: 

```bash 
python "1.1 Agentic Loops/step1_tools.py" 
``` 

Steps that call the API (step 2 onward) need a real key in `.env`. Steps that 
only define data (step 1) run without one. 

## Notes 

- Model defaults to `claude-haiku-4-5` (low cost) — this is practice. 
- Never commit `.env`; it holds your real key and is git-ignored. 
- Add any new dependency to `requirements.txt` (pinned) when you install it. 