"""
File name: hub_spoke_research_coordinator.py

Purpose:
    Demonstrate a hub-and-spoke multi-agent architecture using Python and the
    Anthropic Claude SDK.

    The coordinator is the central hub. It owns the complete orchestration
    workflow:

        1. Decomposition: Break a broad research topic into smaller tasks.
        2. Delegation: Select the appropriate specialist for each task.
        3. Aggregation: Combine specialist findings into a structured report.
        4. Refinement: Identify coverage gaps, delegate follow-up tasks, and
           improve the initial report.

    Specialist agents do not decide how the overall research workflow is
    organized. The coordinator retains responsibility for task assignment,
    workflow control, and final report generation.

Important implementation note:
    This example uses Claude API calls to demonstrate agent orchestration.
    The web_search_agent is a specialist role, not a live browser integration.
    To perform actual online searches, connect a search API or an appropriate
    Claude web-search tool. Similarly, the document analysis specialist does
    not automatically have access to local files or document repositories.

Prerequisites:
    - The Anthropic Python SDK is installed.
    - The .env file contains ANTHROPIC_API_KEY.
    - python-dotenv is installed to load the .env file.
    - ANTHROPIC_MODEL can optionally specify the Claude model to use.
    - RESEARCH_TOPIC can optionally specify the research topic.

Example environment variables:
    ANTHROPIC_API_KEY=your-api-key
    ANTHROPIC_MODEL=claude-sonnet-4-6
    RESEARCH_TOPIC=How can generative AI improve healthcare operations?
"""

import asyncio  # Runs independent specialist agents concurrently, reducing
                 # the time needed compared with calling each agent sequentially.

import json  # Parses JSON returned by Claude and prints the final report in a
             # readable, structured format.

import os  # Reads configuration such as the Claude model and research topic
           # from environment variables instead of hardcoding them.

from anthropic import AsyncAnthropic  # Provides the asynchronous Claude API
                                      # client required for concurrent API calls.

from dotenv import load_dotenv  # Loads configuration and API credentials from
                                # the project's .env file into environment variables.


# Load environment variables before creating the Anthropic client.
# This allows the SDK to find ANTHROPIC_API_KEY without hardcoding credentials.
load_dotenv()


# ---------------------------------------------------------------------------
# 1. Define the available specialist agents
# ---------------------------------------------------------------------------
#
# Each entry describes a specialist's name, responsibilities, and system
# prompt. Keeping these definitions separate from the coordinator makes the
# architecture extensible: additional specialist agents can be registered
# without rewriting the entire orchestration workflow.
#
# The coordinator uses these definitions to select and instruct subagents.
# The specialist agents focus on their assigned tasks rather than controlling
# the overall workflow.
#
# Important: These are specialist definitions, not independent autonomous
# programs. In this example, each specialist is executed through a Claude API
# call. Additional integrations can give individual specialists access to
# dedicated tools, services, APIs, or document repositories.

SUBAGENT_DEFINITIONS = {
    "web_search_agent": {
        "display_name": "Web research specialist",
        "description": (
            "Investigates public information, research questions, industry "
            "trends, competing perspectives, and externally verifiable claims."
        ),
        "system_prompt": """
You are a specialist research agent in a hub-and-spoke architecture.

Your responsibility is to investigate the research question assigned by
the central coordinator and return concise, useful findings.

Follow these rules:

1. Stay within the scope of the assigned research question.
2. Separate established knowledge from assumptions and uncertainty.
3. Highlight claims that require current external verification.
4. Never invent URLs, citations, statistics, or research findings.
5. Do not claim that you performed a live web search unless an actual
   search tool was provided and successfully used.
6. Return your findings as valid JSON with the following structure:

{
    "findings": [
        "Finding one",
        "Finding two"
    ],
    "evidence": [
        "Evidence available in the supplied context"
    ],
    "uncertainties": [
        "Information requiring verification"
    ]
}

The central coordinator will combine your output with findings from other
specialists. Do not attempt to produce the final research report yourself.
""",
    },

    "doc_analysis_agent": {
        "display_name": "Document analysis specialist",
        "description": (
            "Analyzes supplied documentation, frameworks, evidence, "
            "assumptions, limitations, and relationships between findings."
        ),
        "system_prompt": """
You are a document analysis specialist in a hub-and-spoke architecture.

Your responsibility is to analyze the evidence and contextual material
provided with the assigned research question.

Follow these rules:

1. Focus on documentation, frameworks, terminology, evidence quality,
   assumptions, limitations, and relationships between findings.
2. Analyze only material actually supplied in the task or conversation.
3. Never claim to have read a file, report, or document that was not supplied.
4. Identify missing documentation or evidence when it affects conclusions.
5. Distinguish supported conclusions from interpretations and assumptions.
6. Return your findings as valid JSON with the following structure:

{
    "findings": [
        "Finding one",
        "Finding two"
    ],
    "evidence": [
        "Evidence available in the supplied context"
    ],
    "uncertainties": [
        "Information requiring further investigation"
    ]
}

The central coordinator owns the overall research workflow and final report.
Do not independently redefine the entire research assignment.
""",
    },
}


# ---------------------------------------------------------------------------
# 2. Implement the coordinator
# ---------------------------------------------------------------------------
#
# This class represents the central hub in the architecture.
#
# Its responsibilities include:
#   - Understanding the broad research topic.
#   - Decomposing the topic into actionable research tasks.
#   - Selecting specialists for those tasks.
#   - Delegating tasks and collecting specialist responses.
#   - Aggregating the responses into a structured report.
#   - Performing one bounded refinement cycle when gaps are identified.
#
# Keeping these responsibilities in the coordinator is central to the
# hub-and-spoke design. The subagents perform specialist work, while the
# coordinator retains control over orchestration and final output.

class ResearchCoordinator:

    def __init__(self, client: AsyncAnthropic, model: str):
        """
        Initialize the central coordinator.

        Args:
            client:
                The shared asynchronous Anthropic client. Reusing one client
                avoids creating a separate HTTP client for every subagent.

            model:
                The Claude model used for decomposition, specialist research,
                aggregation, and refinement.
        """

        self.client = client
        self.model = model

        # This system prompt defines the coordinator's role and boundaries.
        #
        # It is important to explicitly define the coordinator as the hub.
        # Without these instructions, a model might focus on answering the
        # original topic directly instead of decomposing the work, delegating
        # specialist tasks, and combining their findings.
        self.system_prompt = """
You are the central research coordinator in a hub-and-spoke multi-agent
architecture.

You are responsible for the complete research workflow.

Your responsibilities are:

1. DECOMPOSITION
   Break broad research topics into focused, complementary research tasks.

2. SPECIALIST SELECTION
   Select the most appropriate available specialist for every task.

3. DELEGATION
   Assign tasks to the available specialists. Do not attempt to perform all
   specialist work yourself when a specialist is available.

4. AGGREGATION
   Combine specialist findings, reconcile overlapping information, identify
   contradictions, and prepare one coherent research report.

5. REFINEMENT
   Identify missing coverage and request targeted follow-up research when
   that would materially improve the report.

Available specialist agents:
- web_search_agent
- doc_analysis_agent

The web_search_agent investigates research questions and information that
may require external verification. No live search capability is assumed
unless a search tool is explicitly provided.

The doc_analysis_agent evaluates supplied documentation, evidence,
frameworks, assumptions, and limitations. It cannot access documents that
have not been supplied or connected.

You own task decomposition, specialist selection, delegation, aggregation,
and decisions about refinement.

Specialists own the execution of their assigned research tasks.

Never invent evidence or claim that a task was completed when it was not.
Do not treat unverified information as confirmed facts.

Follow the requested JSON structures exactly whenever JSON is requested.
Return valid JSON without Markdown fences when a task requires JSON output.
"""

    # -----------------------------------------------------------------------
    # Helper: Send a prompt to Claude and parse its JSON response
    # -----------------------------------------------------------------------

    async def _ask_for_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2500,
    ):
        """
        Send an asynchronous Claude request and parse its JSON response.

        JSON is used because coordinator stages need predictable data
        structures, such as task lists and research-report fields.

        A model-generated response may occasionally contain explanatory text
        or Markdown fences around its JSON. The parser therefore searches for
        a valid JSON object or array inside the response.

        Raises:
            ValueError:
                If the response does not contain valid JSON.
            Exception:
                Any API or network error is allowed to propagate so the caller
                can report a genuine failure rather than silently hiding it.
        """

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )

        # Claude responses can contain different content block types.
        # Collect text blocks instead of assuming that the response consists
        # of exactly one text block.
        response_text = "\n".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        )

        # Try parsing the entire response first. If the response includes
        # surrounding explanatory text or Markdown fences, attempt to parse
        # the first valid JSON value found within it.
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()

            for position, character in enumerate(response_text):
                if character not in "[{":
                    continue

                try:
                    parsed_value, _ = decoder.raw_decode(
                        response_text[position:]
                    )
                    return parsed_value
                except json.JSONDecodeError:
                    # This opening bracket did not begin a valid JSON value.
                    # Continue searching for the start of the actual payload.
                    continue

        raise ValueError(
            "Claude returned a response that did not contain valid JSON."
        )

    # -----------------------------------------------------------------------
    # Helper: Choose a fallback specialist
    # -----------------------------------------------------------------------

    @staticmethod
    def _fallback_specialist(research_text: str) -> str:
        """
        Select a specialist when Claude omits or returns an invalid
        specialist identifier during decomposition.

        The coordinator normally delegates according to the model-generated
        task assignment. This small rule-based fallback keeps the workflow
        usable when the generated specialist name is missing or invalid.

        A production system could replace this fallback with a more
        sophisticated routing policy or capability-based agent registry.
        """

        text = research_text.lower()

        document_keywords = (
            "document",
            "documentation",
            "policy",
            "report analysis",
            "framework",
            "evidence quality",
            "limitations",
            "assumptions",
            "compare findings",
        )

        if any(keyword in text for keyword in document_keywords):
            return "doc_analysis_agent"

        # General research is delegated to the research specialist by default.
        return "web_search_agent"

    # -----------------------------------------------------------------------
    # Helper: Normalize tasks produced by the coordinator
    # -----------------------------------------------------------------------

    def _normalise_tasks(
        self,
        raw_tasks: list,
        fallback_topic: str,
        max_tasks: int = 5,
    ) -> list[dict]:
        """
        Validate and normalize the tasks returned by Claude.

        This step is necessary because model-generated JSON can be structurally
        valid while containing missing fields or unknown specialist names.

        The coordinator ensures that every delegated task has:
            - A subtopic.
            - A specific research question.
            - A registered specialist.
            - A reason explaining the task's purpose.

        The task limit helps keep the example bounded in cost and complexity.
        """

        normalised_tasks = []

        for item in raw_tasks:
            # Each task should be a JSON object. Ignore malformed entries
            # rather than allowing them to break the entire workflow.
            if not isinstance(item, dict):
                continue

            subtopic = str(
                item.get("subtopic")
                or item.get("title")
                or ""
            ).strip()

            research_question = str(
                item.get("research_question")
                or item.get("question")
                or subtopic
            ).strip()

            if not subtopic:
                continue

            # Only agents present in the registry may receive delegated tasks.
            # This prevents a generated task from referring to a nonexistent
            # specialist.
            specialist = str(
                item.get("specialist") or ""
            ).strip().lower().replace(" ", "_")

            # Support a few common alternative names returned by models.
            aliases = {
                "websearchagent": "web_search_agent",
                "web_search": "web_search_agent",
                "docanalysisagent": "doc_analysis_agent",
                "document_analysis_agent": "doc_analysis_agent",
                "document_analysis": "doc_analysis_agent",
            }

            specialist = aliases.get(specialist, specialist)

            if specialist not in SUBAGENT_DEFINITIONS:
                specialist = self._fallback_specialist(
                    f"{subtopic} {research_question}"
                )

            normalised_tasks.append(
                {
                    "subtopic": subtopic,
                    "research_question": research_question,
                    "specialist": specialist,
                    "reason": str(
                        item.get("reason")
                        or "Investigate this part of the overall topic."
                    ).strip(),
                }
            )

            if len(normalised_tasks) >= max_tasks:
                break

        # Ensure that even a poor decomposition response produces a usable
        # task rather than leaving the coordinator with nothing to delegate.
        if not normalised_tasks:
            normalised_tasks.append(
                {
                    "subtopic": fallback_topic,
                    "research_question": (
                        f"Identify the most important findings, evidence, "
                        f"risks, and unanswered questions about: "
                        f"{fallback_topic}"
                    ),
                    "specialist": "web_search_agent",
                    "reason": (
                        "Fallback task created because no valid tasks "
                        "were returned by decomposition."
                    ),
                }
            )

        return normalised_tasks

    # -----------------------------------------------------------------------
    # Phase 1: Decomposition
    # -----------------------------------------------------------------------

    async def decompose(self, topic: str) -> list[dict]:
        """
        Break a broad research topic into smaller, manageable tasks.

        Decomposition is owned by the coordinator because the coordinator
        understands the overall research objective and can plan complementary
        tasks across multiple specialists.

        Each task includes an explicit specialist assignment. The specialist
        does not independently decide the overall task structure.
        """

        prompt = f"""
Decompose the following broad research topic into focused research tasks.

Research topic:
{topic}

Available specialists and their capabilities:
{json.dumps(SUBAGENT_DEFINITIONS, indent=2)}

Requirements:
1. Generate between 3 and 5 complementary tasks.
2. Avoid unnecessary overlap between tasks.
3. Cover important perspectives, risks, opportunities, and uncertainties.
4. Assign every task to exactly one available specialist.
5. Use only these specialist identifiers:
   - web_search_agent
   - doc_analysis_agent
6. Explain why each task matters to the overall research objective.
7. Make each research question specific enough to delegate independently.

Return only a JSON object in this format:

{{
    "tasks": [
        {{
            "subtopic": "A concise task title",
            "research_question": "A focused question to investigate",
            "specialist": "web_search_agent",
            "reason": "Why this task is required"
        }}
    ]
}}
"""

        decomposition = await self._ask_for_json(
            self.system_prompt,
            prompt,
        )

        raw_tasks = (
            decomposition.get("tasks", [])
            if isinstance(decomposition, dict)
            else []
        )

        tasks = self._normalise_tasks(
            raw_tasks=raw_tasks,
            fallback_topic=topic,
            max_tasks=5,
        )

        print(
            f"[COORDINATOR] Decomposed the topic into {len(tasks)} task(s)."
        )
        # Example output:
        # [COORDINATOR] Decomposed the topic into 4 task(s).
        #
        # The actual task count depends on Claude's decomposition response.

        # Display the task assignments so we can see how the hub distributes
        # responsibilities across the available specialist agents.
        for index, task in enumerate(tasks, start=1):
            print(
                f"[COORDINATOR] Task {index}: "
                f"{task['subtopic']} -> {task['specialist']}"
            )
            # Example output:
            # [COORDINATOR] Task 1: Healthcare use cases -> web_search_agent
            #
            # The actual task title and specialist may differ.

        return tasks

    # -----------------------------------------------------------------------
    # Phase 2: Delegate tasks to specialist agents
    # -----------------------------------------------------------------------

    async def _run_subagent(self, task: dict) -> dict:
        """
        Execute one specialist's assigned research task.

        Each specialist receives:
            - Its own system prompt.
            - The specific task selected by the coordinator.
            - The original research objective for context.

        Independent tasks are executed concurrently by delegate(). This
        avoids waiting for each API call to finish before starting the next.

        The specialist returns findings in a consistent JSON structure so
        the coordinator can aggregate results without relying on free-form
        prose alone.
        """

        specialist_name = task["specialist"]
        specialist = SUBAGENT_DEFINITIONS[specialist_name]

        print(
            f"[SUBAGENT] {specialist_name} started: "
            f"{task['subtopic']}"
        )
        # Example output:
        # [SUBAGENT] web_search_agent started: Healthcare use cases
        #
        # Specialist start messages may appear in different orders because
        # the delegated API calls run concurrently.

        system_prompt = specialist["system_prompt"]

        user_prompt = f"""
Execute the research task assigned by the central coordinator.

Assigned specialist:
{specialist["display_name"]}

Specialist responsibilities:
{specialist["description"]}

Subtopic:
{task["subtopic"]}

Research question:
{task["research_question"]}

Reason for assignment:
{task["reason"]}

Your output will be used by the central coordinator to prepare a report.
Return findings that directly address the assigned research question.

Return only a JSON object in this format:

{{
    "findings": [
        "A concise finding relevant to the research question"
    ],
    "evidence": [
        "Supporting evidence or the basis for the conclusion"
    ],
    "uncertainties": [
        "An unresolved question or limitation"
    ]
}}
"""

        specialist_response = await self._ask_for_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Normalize the specialist's response so downstream aggregation can
        # expect a consistent schema, even if one field is missing.
        if not isinstance(specialist_response, dict):
            specialist_response = {}

        findings = specialist_response.get("findings", [])
        evidence = specialist_response.get("evidence", [])
        uncertainties = specialist_response.get("uncertainties", [])

        # If the model returns a single string rather than a list, convert it
        # to a list to preserve the output contract.
        if isinstance(findings, str):
            findings = [findings]

        if isinstance(evidence, str):
            evidence = [evidence]

        if isinstance(uncertainties, str):
            uncertainties = [uncertainties]

        result = {
            "subtopic": task["subtopic"],
            "research_question": task["research_question"],
            "specialist": specialist_name,
            "findings": findings if isinstance(findings, list) else [],
            "evidence": evidence if isinstance(evidence, list) else [],
            "uncertainties": (
                uncertainties if isinstance(uncertainties, list) else []
            ),
        }

        print(
            f"[SUBAGENT] {specialist_name} completed: "
            f"{task['subtopic']} "
            f"({len(result['findings'])} finding(s))."
        )
        # Example output:
        # [SUBAGENT] web_search_agent completed: Healthcare use cases (3 finding(s)).
        #
        # Finding counts and completion order depend on each response.

        return result

    async def delegate(self, tasks: list[dict]) -> list[dict]:
        """
        Delegate tasks to their assigned specialist agents.

        asyncio.gather() starts the independent tasks concurrently. The
        coordinator still owns the task list and decides which specialist
        receives each task; concurrency does not transfer orchestration
        responsibility to the subagents.

        asyncio.gather() returns the results in the order of the supplied
        awaitables, even if the individual tasks finish in a different order.
        """

        print(
            f"[COORDINATOR] Delegating {len(tasks)} task(s) "
            "to specialist agents."
        )
        # Example output:
        # [COORDINATOR] Delegating 4 task(s) to specialist agents.

        delegated_results = await asyncio.gather(
            *(self._run_subagent(task) for task in tasks)
        )

        print(
            f"[COORDINATOR] Received {len(delegated_results)} "
            "specialist result(s)."
        )
        # Example output:
        # [COORDINATOR] Received 4 specialist result(s).

        return delegated_results

    # -----------------------------------------------------------------------
    # Phase 3: Aggregation
    # -----------------------------------------------------------------------

    async def aggregate(
        self,
        topic: str,
        specialist_results: list[dict],
        previous_report: dict | None = None,
    ) -> dict:
        """
        Combine specialist findings into a structured research report.

        Aggregation is a coordinator responsibility. Individual specialists
        return limited, task-specific findings; the coordinator synthesizes
        those findings into a coherent report covering the original topic.

        If a previous draft is supplied, the coordinator uses it during the
        refinement cycle to preserve useful findings and incorporate new
        evidence instead of starting over without context.
        """

        print(
            f"[COORDINATOR] Aggregating "
            f"{len(specialist_results)} specialist result(s)."
        )
        # Example output:
        # [COORDINATOR] Aggregating 4 specialist result(s).

        previous_report_text = (
            json.dumps(previous_report, indent=2)
            if previous_report is not None
            else "No previous report exists. Create the initial report."
        )

        prompt = f"""
Create a structured research report using the specialist results below.

Original research topic:
{topic}

Specialist results:
{json.dumps(specialist_results, indent=2)}

Previous draft:
{previous_report_text}

Your responsibilities as coordinator:

1. Combine related findings without unnecessary repetition.
2. Resolve apparent contradictions when the available evidence supports
   a reasonable resolution.
3. Preserve meaningful disagreements and uncertainties when they cannot
   be resolved.
4. Identify gaps in the coverage of the original topic.
5. Incorporate useful information from the previous draft if one exists.
6. During refinement, remove a coverage gap only when the additional findings
   sufficiently address it.
7. Do not invent sources, statistics, citations, or verification.
8. Clearly identify claims that require external verification.

Return only a JSON object using this structure:

{{
    "title": "A suitable research report title",
    "research_topic": "{topic}",
    "executive_summary": "A concise summary of the overall findings",
    "key_findings": [
        {{
            "finding": "The finding",
            "supporting_evidence": [
                "Evidence from the specialist results"
            ],
            "confidence": "High, Medium, or Low"
        }}
    ],
    "cross_cutting_insights": [
        "Insight that emerges from multiple findings"
    ],
    "coverage_gaps": [
        "An important question that remains insufficiently addressed"
    ],
    "recommendations": [
        "An actionable recommendation based on the findings"
    ],
    "sources_and_caveats": [
        "Evidence limitations, verification requirements, or source caveats"
    ]
}}

Use an empty list for any section with no applicable entries.
Confidence describes the strength of the supplied support, not a claim that
the finding has been independently verified.
"""

        report = await self._ask_for_json(
            system_prompt=self.system_prompt,
            user_prompt=prompt,
            max_tokens=4000,
        )

        if not isinstance(report, dict):
            raise ValueError(
                "The coordinator did not return a valid report object."
            )

        # Keep the report's most important collections predictable.
        # This also avoids calling list operations on malformed field values.
        list_fields = (
            "key_findings",
            "cross_cutting_insights",
            "coverage_gaps",
            "recommendations",
            "sources_and_caveats",
        )

        for field in list_fields:
            if not isinstance(report.get(field), list):
                report[field] = []

        report.setdefault("title", f"Research report: {topic}")
        report.setdefault("research_topic", topic)
        report.setdefault("executive_summary", "")

        return report

    # -----------------------------------------------------------------------
    # Phase 4: Refinement
    # -----------------------------------------------------------------------

    async def create_refinement_tasks(
        self,
        topic: str,
        report: dict,
    ) -> list[dict]:
        """
        Convert the coverage gaps in the current report into targeted tasks.

        This stage demonstrates coordinator-controlled refinement.

        Rather than asking every specialist to repeat its original work,
        the coordinator identifies unanswered questions and delegates only
        the additional work that could materially improve the report.

        The example allows at most one refinement cycle in research().
        This bound makes the workflow easier to reason about and helps prevent
        uncontrolled repeated delegation and excessive API usage.
        """

        coverage_gaps = report.get("coverage_gaps", [])

        # Nothing needs refinement when the initial report has no identified
        # coverage gaps. Skipping unnecessary follow-up work saves resources.
        if not coverage_gaps:
            print(
                "[COORDINATOR] No material coverage gaps identified; "
                "skipping refinement."
            )
            # Example output:
            # [COORDINATOR] No material coverage gaps identified; skipping refinement.

            return []

        prompt = f"""
The research coordinator has identified the following coverage gaps.

Original topic:
{topic}

Current report:
{json.dumps(report, indent=2)}

Coverage gaps:
{json.dumps(coverage_gaps, indent=2)}

Generate targeted follow-up research tasks that address the most important
gaps. Do not repeat research that has already been adequately covered.

Available specialists:
{json.dumps(SUBAGENT_DEFINITIONS, indent=2)}

Requirements:
1. Generate no more than 3 targeted tasks.
2. Each task must address a specific coverage gap.
3. Assign each task to an available specialist.
4. Use only web_search_agent or doc_analysis_agent.
5. If the available context is insufficient to resolve a gap, explicitly
   investigate what information is missing.
6. Prefer useful follow-up research over repeating existing findings.

Return only this JSON structure:

{{
    "tasks": [
        {{
            "subtopic": "Targeted follow-up task",
            "research_question": "The specific unresolved question",
            "specialist": "doc_analysis_agent",
            "reason": "Which coverage gap this task addresses"
        }}
    ]
}}
"""

        refinement_response = await self._ask_for_json(
            system_prompt=self.system_prompt,
            user_prompt=prompt,
        )

        raw_tasks = (
            refinement_response.get("tasks", [])
            if isinstance(refinement_response, dict)
            else []
        )

        tasks = self._normalise_tasks(
            raw_tasks=raw_tasks,
            fallback_topic=topic,
            max_tasks=3,
        )

        # The normalization method provides a general fallback task. For a
        # refinement cycle, replace that fallback with tasks explicitly linked
        # to the coverage gaps when the model returns no valid assignments.
        if (
            len(tasks) == 1
            and tasks[0]["subtopic"] == topic
            and not raw_tasks
        ):
            tasks = []

            for gap in coverage_gaps[:3]:
                gap_text = str(gap).strip()

                if not gap_text:
                    continue

                specialist = self._fallback_specialist(gap_text)

                tasks.append(
                    {
                        "subtopic": f"Refinement: {gap_text}",
                        "research_question": (
                            f"What additional information is needed to "
                            f"address this coverage gap: {gap_text}"
                        ),
                        "specialist": specialist,
                        "reason": (
                            "Targeted follow-up for an unresolved "
                            "coverage gap in the initial report."
                        ),
                    }
                )

        print(
            f"[COORDINATOR] Generated {len(tasks)} "
            "targeted refinement task(s)."
        )
        # Example output:
        # [COORDINATOR] Generated 2 targeted refinement task(s).

        return tasks

    # -----------------------------------------------------------------------
    # Main orchestration workflow
    # -----------------------------------------------------------------------

    async def research(self, topic: str) -> dict:
        """
        Execute the complete hub-and-spoke research workflow.

        Workflow:
            1. Accept the broad research topic.
            2. Decompose the topic into focused subtasks.
            3. Delegate subtasks to specialist agents concurrently.
            4. Aggregate specialist responses into a report.
            5. Inspect coverage gaps.
            6. If necessary, perform one targeted refinement cycle.
            7. Return the final structured report.

        The coordinator owns every orchestration decision throughout this
        workflow. Specialist agents execute individual tasks but do not
        control the overall research process.
        """

        topic = topic.strip()

        if not topic:
            raise ValueError("The research topic must not be empty.")

        print(f"\n[COORDINATOR] Received research topic: {topic}")
        # Example output:
        # [COORDINATOR] Received research topic: How can generative AI improve healthcare operations?

        # Phase 1: The coordinator decomposes the overall topic and assigns
        # a specialist to each focused research task.
        tasks = await self.decompose(topic)

        # Phase 2: The coordinator delegates tasks and collects their results.
        initial_results = await self.delegate(tasks)

        # Phase 3: The coordinator aggregates all initial specialist results.
        report = await self.aggregate(
            topic=topic,
            specialist_results=initial_results,
        )

        coverage_gaps = report.get("coverage_gaps", [])

        if coverage_gaps:
            print(
                f"[COORDINATOR] Identified {len(coverage_gaps)} "
                "potential coverage gap(s); starting refinement."
            )
            # Example output:
            # [COORDINATOR] Identified 2 potential coverage gap(s); starting refinement.
            #
            # The actual number of gaps depends on the aggregated report.

            # Ask the coordinator to generate additional tasks that directly
            # address the most important gaps in the initial report.
            refinement_tasks = await self.create_refinement_tasks(
                topic=topic,
                report=report,
            )

            if refinement_tasks:
                # Delegate follow-up tasks using the same specialist registry
                # and execution mechanism. No new orchestration mechanism is
                # needed for the refinement cycle.
                refinement_results = await self.delegate(refinement_tasks)

                # Merge initial and follow-up results before creating the
                # revised report. Passing the previous draft preserves useful
                # details and gives the coordinator context for resolving gaps.
                all_results = initial_results + refinement_results

                report = await self.aggregate(
                    topic=topic,
                    specialist_results=all_results,
                    previous_report=report,
                )

                print(
                    "[COORDINATOR] Refinement completed. "
                    "The report has been updated with follow-up findings."
                )
                # Example output:
                # [COORDINATOR] Refinement completed. The report has been updated with follow-up findings.

        print("[COORDINATOR] Research workflow completed.")
        # Example output:
        # [COORDINATOR] Research workflow completed.

        return report


# ---------------------------------------------------------------------------
# 3. Application entry point
# ---------------------------------------------------------------------------
#
# This function wires together the shared Claude client and the coordinator.
# The topic can be supplied through RESEARCH_TOPIC, allowing the same Python
# file to be reused for different research assignments without code changes.
#
# A single AsyncAnthropic client is shared by all specialist executions.
# The asynchronous context manager also ensures that client resources are
# properly closed after the workflow completes or fails.

async def main():
    # Read the requested research topic from the environment. The default
    # provides a useful example when no custom topic is configured.
    topic = os.getenv(
        "RESEARCH_TOPIC",
        "How can generative AI improve healthcare operations?",
    )

    # Allow the model to be changed through configuration instead of requiring
    # source-code modification. Set this variable to a model identifier
    # supported by the account and installed SDK.
    model = os.getenv(
        "ANTHROPIC_MODEL",
        "claude-sonnet-4-6",
    )

    try:
        async with AsyncAnthropic() as client:

            # Instantiate the coordinator with the shared Claude client.
            coordinator = ResearchCoordinator(
                client=client,
                model=model,
            )

            # Run the orchestration workflow and receive a structured report.
            research_report = await coordinator.research(topic)

            # Print the final report as readable JSON.
            print("\n[REPORT] Structured research report:")
            # Example output:
            # [REPORT] Structured research report:

            print(
                json.dumps(
                    research_report,
                    indent=2,
                    ensure_ascii=False,
                )
            )
            # Example output (illustrative only; actual content varies):
            #
            # {
            #   "title": "Generative AI in Healthcare Operations",
            #   "research_topic": "How can generative AI improve healthcare operations?",
            #   "executive_summary": "Generative AI may help automate
            #     administrative tasks and improve access to information.",
            #   "key_findings": [
            #     {
            #       "finding": "Administrative workflow automation is
            #         a potential use case.",
            #       "supporting_evidence": [
            #         "Illustrative finding from a specialist agent."
            #       ],
            #       "confidence": "Medium"
            #     }
            #   ],
            #   "cross_cutting_insights": [
            #     "Data quality and human oversight affect adoption."
            #   ],
            #   "coverage_gaps": [
            #     "Current implementation costs require verification."
            #   ],
            #   "recommendations": [
            #     "Validate a pilot using measurable operational KPIs."
            #   ],
            #   "sources_and_caveats": [
            #     "Live web retrieval is not configured in this example."
            #   ]
            # }
            #
            # This JSON illustrates the output structure, not verified
            # research conclusions or guaranteed model-generated content.

    except Exception as exc:
        # Surface configuration errors, API errors, parsing errors, and other
        # unexpected failures instead of returning a misleading success result.
        print(f"[ERROR] Research workflow failed: {exc}")
        # Example output:
        # [ERROR] Research workflow failed: AuthenticationError(...)
        #
        # The actual error depends on the cause, such as invalid credentials,
        # an unsupported model identifier, a network issue, or malformed JSON.


# Run the asynchronous application when this file is executed directly.
# The guard prevents the workflow from running automatically if the module
# is imported by another Python file for reuse or testing.
if __name__ == "__main__":
    asyncio.run(main())