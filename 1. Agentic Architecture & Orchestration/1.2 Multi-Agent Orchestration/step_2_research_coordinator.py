"""
STEP 2: Broad decomposition (at least 5 subtopics covering the WHOLE topic).

CHANGE LOG
----------
Carried over from STEP 1 (marked [STEP 1]):
    - ask_claude() and parse_json_list() helpers
    - the 2 subagents
    - Coordinator: __init__, run_subagent(), delegate(), aggregate(), research()

New or changed in STEP 2 (marked [STEP 2]):
    - NEW constant   : MIN_SUBTOPICS
    - NEW methods    : list_categories(), find_missing(), assign_agents()
    - CHANGED method : decompose()  (was one question, now 3 small phases)
    - CHANGED demo   : main() checks that the decomposition is broad enough

Why step 2 exists
-----------------
Imagine the topic "renewable energy" and a coordinator that only creates
"solar" and "wind". Every subagent can do perfect work and the final report
is STILL incomplete, because geothermal, tidal, biomass and fusion were never
assigned. The mistake is in the coordinator's decomposition, not the
subagents. We prevent it with 3 phases:
    Phase 1: list ALL categories first (this forces breadth)
    Phase 2: ask "what is missing?" (a second look finds forgotten areas)
    Phase 3: turn every category into a question for a subagent
"""

import asyncio  # Lets us run several Claude calls at the same time.
import json  # Turns Claude's JSON text answer into Python lists/dicts.
import logging  # Prints progress messages with a level (INFO, WARNING...).

import anthropic  # The official Claude SDK; gives us the Claude client.
from dotenv import load_dotenv  # Reads your API key from the .env file.

# ---------------------------------------------------------------------------
# Setup  [STEP 1]
# ---------------------------------------------------------------------------
load_dotenv()  # Must run before creating the client so it can find the key.

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("coordinator")

MODEL = "claude-sonnet-5-5"
client = anthropic.AsyncAnthropic()  # The async version, used with `await`.

# [STEP 2 - NEW] The exercise says "at least 5 subtopics". Naming the number
# once means we can reuse it in prompts and checks without typing 5 everywhere.
MIN_SUBTOPICS = 5


async def ask_claude(system_prompt, user_prompt):  # [STEP 1]
    """Send one prompt to Claude and return its text answer."""
    response = await client.messages.create(
        model=MODEL,
        max_tokens=2000,  # Maximum length of the answer (also limits cost).
        system=system_prompt,  # Tells Claude WHO it is for this call.
        messages=[{"role": "user", "content": user_prompt}],  # The task.
    )
    return response.content[0].text


def parse_json_list(text):  # [STEP 1]
    """Pull a JSON list out of Claude's answer.

    We cut out everything between the first '[' and the last ']' because
    Claude sometimes adds extra words or ```json fences around the list.
    """
    start = text.find("[")
    end = text.rfind("]") + 1
    return json.loads(text[start:end])


# ---------------------------------------------------------------------------
# The subagents (the "spokes")  [STEP 1]
# ---------------------------------------------------------------------------
web_search_agent = {
    "name": "web_search_agent",
    "description": "Finds current public information: news, trends, market data.",
    "system_prompt": (
        "You are a web research specialist. Answer ONLY the question you are "
        "given. Be concise and say which source each claim comes from."
    ),
}

doc_analysis_agent = {
    "name": "doc_analysis_agent",
    "description": "Analyzes technical material: papers, standards, reports.",
    "system_prompt": (
        "You are a document analysis specialist. Answer ONLY the question you "
        "are given. Focus on depth and precision, and name your sources."
    ),
}


# ---------------------------------------------------------------------------
# The coordinator (the "hub")
# ---------------------------------------------------------------------------
class Coordinator:
    def __init__(self, subagents):  # [STEP 1]
        self.subagents = {agent["name"]: agent for agent in subagents}
        agent_list = "\n".join(f"- {a['name']}: {a['description']}" for a in subagents)
        self.system_prompt = (
            "You are a research coordinator. You do NOT research yourself. "
            "You split topics into subtopics, assign each to the best "
            "specialist subagent, and combine their results into a report.\n\n"
            "Available subagents:\n" + agent_list
        )

    # -------- Decomposition: 3 small phases (all [STEP 2 - NEW]) --------

    async def list_categories(self, topic, hint=""):
        """PHASE 1: list every major category of the topic.

        Why categories first? If we ask directly for subtopics, Claude grabs
        the two or three most famous areas and stops. Asking for a full list
        of categories first makes it think about the whole topic.
        `hint` is empty at first; on a retry it says "that was too short".
        """
        prompt = (
            f"Topic: {topic}\n\n"
            "List ALL major categories of this topic. Missing a whole "
            "category is a critical failure, because nobody can research an "
            "area that was never assigned. Include established areas, "
            "emerging or experimental areas, and cross-cutting areas such as "
            f"economics, policy and risks. Give at least {MIN_SUBTOPICS}. "
            f"{hint}\n"
            'Reply with ONLY a JSON list of short names, like: ["Category A", "Category B"]'
        )
        return parse_json_list(await ask_claude(self.system_prompt, prompt))

    async def find_missing(self, topic, categories):
        """PHASE 2: ask Claude to review the list and name what is missing.

        Why a second pass? Spotting a hole in a finished list is easier than
        writing a perfect list in one go. Returns [] if nothing is missing.
        """
        prompt = (
            f"Topic: {topic}\n\nCategories so far: {', '.join(categories)}\n\n"
            "Act as a strict reviewer. Which MAJOR categories of this topic "
            "are missing? Do not repeat existing ones and do not add minor "
            "details.\n"
            "Reply with ONLY a JSON list of missing category names, or [] if "
            "nothing important is missing."
        )
        return parse_json_list(await ask_claude(self.system_prompt, prompt))

    async def assign_agents(self, topic, categories):
        """PHASE 3: turn each category into a question for one subagent."""
        example = '[{"subtopic": "a clear question", "agent": "web_search_agent"}]'
        prompt = (
            f"Topic: {topic}\n\nCategories:\n- " + "\n- ".join(categories) + "\n\n"
            "Turn EACH category into exactly one subtopic. Do not skip any. "
            "Write each subtopic as a complete question that names its "
            "subject clearly, because the subagent will not see the topic. "
            f"Assign each to one of: {', '.join(self.subagents)}.\n"
            f"Reply with ONLY a JSON list like this: {example}"
        )
        return parse_json_list(await ask_claude(self.system_prompt, prompt))

    # [STEP 2 - CHANGED] Before: one call asking for "4 to 6 subtopics".
    async def decompose(self, topic):
        """JOB 1: split the topic into AT LEAST 5 subtopics covering everything."""
        log.info("Decomposing topic: %s", topic)
        # Sample output:
        # INFO: Decomposing topic: Renewable energy

        # Phase 1: list categories. Try up to 3 times if the list is too short.
        categories = []
        hint = ""
        for attempt in range(1, 4):
            categories = await self.list_categories(topic, hint)
            log.info("Attempt %d: found %d categories", attempt, len(categories))
            # Sample output:
            # INFO: Attempt 1: found 8 categories
            if len(categories) >= MIN_SUBTOPICS:
                break  # Long enough, no need to retry.
            hint = f"Your last answer had only {len(categories)}, which is too narrow."
            log.warning("Too few categories, retrying")
            # Sample output:
            # WARNING: Too few categories, retrying

        # Phase 2: add anything that was forgotten (skip names we already have).
        known = {name.lower() for name in categories}
        missing = [m for m in await self.find_missing(topic, categories) if m.lower() not in known]
        if missing:
            log.warning("Audit found missing categories: %s", ", ".join(missing))
            # Sample output:
            # WARNING: Audit found missing categories: Nuclear fusion, Ocean thermal energy
            categories += missing
        else:
            log.info("Audit passed: nothing missing")
            # Sample output:
            # INFO: Audit passed: nothing missing

        # Safety net: warn loudly instead of silently continuing with a narrow list.
        if len(categories) < MIN_SUBTOPICS:
            log.error("Only %d categories, expect gaps in the report", len(categories))
            # Sample output:
            # ERROR: Only 4 categories, expect gaps in the report

        # Phase 3: turn every category into a task for a subagent.
        tasks = await self.assign_agents(topic, categories)
        log.info("Created %d subtopics", len(tasks))
        # Sample output:
        # INFO: Created 10 subtopics
        return tasks

    # -------- Everything below is unchanged from step 1 --------

    async def run_subagent(self, task):  # [STEP 1]
        """Run ONE subagent on ONE subtopic."""
        default_agent = next(iter(self.subagents.values()))
        agent = self.subagents.get(task["agent"], default_agent)
        log.info("Delegating to %s: %s", agent["name"], task["subtopic"])
        # Sample output:
        # INFO: Delegating to doc_analysis_agent: How do tidal energy systems work?
        try:
            return await ask_claude(agent["system_prompt"], task["subtopic"])
        except Exception as error:
            log.error("%s failed: %s", agent["name"], error)
            # Sample output:
            # ERROR: web_search_agent failed: Request timed out.
            return f"FAILED: {error}"

    async def delegate(self, tasks):  # [STEP 1]
        """JOB 2: run all subagents at the same time."""
        answers = await asyncio.gather(*(self.run_subagent(t) for t in tasks))
        log.info("Collected %d answers", len(answers))
        # Sample output:
        # INFO: Collected 10 answers
        return list(answers)

    async def aggregate(self, topic, tasks, answers):  # [STEP 1]
        """JOB 3: combine all answers into one report."""
        log.info("Aggregating results")
        # Sample output:
        # INFO: Aggregating results
        findings = "\n\n".join(
            f"## {task['subtopic']}\n{answer}" for task, answer in zip(tasks, answers)
        )
        prompt = (
            f"Topic: {topic}\n\nResults from subagents:\n\n{findings}\n\n"
            "Write one clear research report. Merge overlaps and clearly "
            "mention any subtopic that FAILED or looks weak."
        )
        return await ask_claude(self.system_prompt, prompt)

    async def research(self, topic):  # [STEP 1]
        """The one method you call: topic in, report out."""
        tasks = await self.decompose(topic)  # now broader (step 2)
        answers = await self.delegate(tasks)
        report = await self.aggregate(topic, tasks, answers)
        return {"topic": topic, "subtopics": tasks, "report": report}


coordinator = Coordinator([web_search_agent, doc_analysis_agent])  # [STEP 1]


# [STEP 2 - CHANGED] Step 1 ran the whole pipeline. Now we only run the
# decomposition and check that it is broad enough (cheaper and faster).
async def main():
    topic = "Renewable energy"
    tasks = await coordinator.decompose(topic)

    print(f"\nSubtopics for '{topic}':")
    for task in tasks:
        print(f"- {task['subtopic']}  (agent: {task['agent']})")
    # Sample output:
    # Subtopics for 'Renewable energy':
    # - How do solar PV and solar thermal technologies compare today?  (agent: web_search_agent)
    # - What is the state of onshore and offshore wind power?  (agent: web_search_agent)
    # - How does geothermal energy work and where is it used?  (agent: doc_analysis_agent)
    # - What is the potential of tidal and wave energy?  (agent: doc_analysis_agent)
    # - How are biomass and biofuels produced and used?  (agent: doc_analysis_agent)
    # - What is the status of nuclear fusion research?  (agent: web_search_agent)
    # ...

    print(f"\nTotal: {len(tasks)} subtopics (minimum required: {MIN_SUBTOPICS})")
    # Sample output:
    # Total: 10 subtopics (minimum required: 5)

    # Simple breadth check: do these key words appear anywhere in the subtopics?
    all_text = " ".join(t["subtopic"].lower() for t in tasks)
    wanted = ["solar", "wind", "geothermal", "tidal", "biomass", "fusion"]
    not_found = [word for word in wanted if word not in all_text]
    if not_found:
        print("BREADTH CHECK FAILED, missing:", ", ".join(not_found))
        # Sample output (only if something is missing):
        # BREADTH CHECK FAILED, missing: fusion
    else:
        print("BREADTH CHECK PASSED: all key areas are covered")
        # Sample output:
        # BREADTH CHECK PASSED: all key areas are covered

    # To run everything (decompose -> delegate -> aggregate), uncomment:
    # result = await coordinator.research(topic)
    # print(result["report"])


if __name__ == "__main__":
    asyncio.run(main())
