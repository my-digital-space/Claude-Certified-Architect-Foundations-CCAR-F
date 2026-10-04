"""
1_a_simple_AI_agent.py

A simple AI agent that demonstrates the basic agentic loop using Claude / Anthropic API style:
1. Receive input
2. Think (use Claude LLM to reason)
3. Respond

This agent uses LangChain's `ChatAnthropic` integration connected to our local mock API server.

Prerequisites:
- Mock API server must be running at http://localhost:8000
- Virtual environment activated with dependencies installed
"""

# ============================================================================
# STEP 1: Import Required Libraries
# ============================================================================

import os
from dotenv import load_dotenv

# LangChain Anthropic integration (native Claude API style)
from langchain_anthropic import ChatAnthropic

# LangChain Core Message types for structured conversation
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables from .env file if it exists
load_dotenv(override=True)


# ============================================================================
# STEP 2: Configure the Claude LLM Connection
# ============================================================================

def create_claude_llm():
    """
    Create and configure the Claude Language Model (LLM) connection.

    This function sets up a connection to our local mock API server using
    LangChain's ChatAnthropic class (Anthropic API format: /v1/messages).

    Returns:
        ChatAnthropic: Configured Claude LLM instance
    """

    # Get configuration from environment variables or use defaults
    anthropic_api_url = os.getenv("ANTHROPIC_API_URL", "http://localhost:8000")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "mock-api-key-001")
    model_name = os.getenv("MODEL_NAME", "claude-3-5-sonnet-20241022")

    # Create the Claude LLM instance using Anthropic native API format
    # Note: anthropic_api_url should be base URL (http://localhost:8000)
    # The SDK automatically appends /v1/messages
    llm = ChatAnthropic(
        anthropic_api_url=anthropic_api_url,  # Local mock server endpoint (base URL)
        anthropic_api_key=anthropic_api_key,  # Mock API key (validated by local server)
        model_name=model_name,                # Claude model name
        temperature=0.7,                      # Controls creativity (0.0 = deterministic, 1.0 = creative)
        max_tokens=1024,                      # Max tokens for the response
    )

    return llm


# ============================================================================
# STEP 3: Define the Agent's System Prompt
# ============================================================================

def get_system_prompt():
    """
    Define the agent's behavior and personality through a system prompt.

    In Claude's API, the system prompt is passed as a top-level `system` parameter
    or as a SystemMessage, providing high-level behavioral guidance.

    Returns:
        str: The system prompt text
    """

    return """You are a helpful AI assistant designed to answer questions clearly and concisely.

Your guidelines:
- Be friendly and professional
- Give direct, accurate answers
- If you don't know something, admit it
- Keep responses focused and relevant
- Use examples when helpful

You are currently running as a simple agent without access to external tools or memory."""


# ============================================================================
# STEP 4: Create the Simple Agent
# ============================================================================

class SimpleAgent:
    """
    A simple AI agent that can respond to user queries.

    This agent demonstrates the basic agentic loop:
    1. Receive input (user message)
    2. Think (send to Claude LLM with system prompt)
    3. Respond (return LLM's answer)
    """

    def __init__(self, llm: ChatAnthropic, system_prompt: str):
        """
        Initialize the agent with a Claude LLM and system prompt.

        Args:
            llm: The ChatAnthropic language model instance
            system_prompt: Instructions that define the agent's behavior
        """
        self.llm = llm
        self.system_prompt = system_prompt

    def run(self, user_input: str) -> str:
        """
        Process a user query and return the agent's response.

        This is the core agentic loop:
        1. Take user input
        2. Combine it with system prompt
        3. Send to Claude LLM
        4. Return response

        Args:
            user_input (str): The user's question or message

        Returns:
            str: The agent's response
        """

        # Step 1: Create the message list
        # We pass SystemMessage for behavior instructions, and HumanMessage for user input
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_input)
        ]

        # Step 2: Send messages to Claude LLM and get response
        print(f"\n[*] Agent is thinking (calling Claude API)...")
        response = self.llm.invoke(messages)

        # Step 3: Extract the text content from the response
        response_text = response.content

        return response_text


# ============================================================================
# STEP 5: Interactive Demo Function
# ============================================================================

def run_interactive_demo():
    """
    Run an interactive demo where you can chat with the Claude agent.

    This allows you to:
    - Ask multiple questions
    - See how the agent responds using Claude
    - Type 'quit' or 'exit' to stop
    """

    print("=" * 70)
    print("  SIMPLE AI AGENT DEMO (CLAUDE API STYLE)")
    print("=" * 70)
    print("\nInitializing agent...")

    # Create the Claude LLM instance
    try:
        llm = create_claude_llm()
        print("[+] Connected to Claude LLM (via mock API)")
    except Exception as e:
        print(f"\n[-] Error connecting to LLM: {e}")
        print("\nMake sure the mock API server is running!")
        print("Start it with: cd ../claude-mock-api && .venv/Scripts/python -m uvicorn app.main:app --port 8000")
        return

    # Get the system prompt
    system_prompt = get_system_prompt()
    print("[+] System prompt configured")

    # Create the agent
    agent = SimpleAgent(llm, system_prompt)
    print("[+] Agent ready!\n")

    print("-" * 70)
    print("You can now chat with the Claude agent.")
    print("Type 'quit' or 'exit' to stop.")
    print("-" * 70)

    # Main interaction loop
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()

        # Check if user wants to quit
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\nGoodbye!")
            break

        # Skip empty inputs
        if not user_input:
            continue

        # Get agent's response
        try:
            response = agent.run(user_input)
            print(f"\nAgent: {response}")
        except Exception as e:
            print(f"\n[-] Error: {e}")
            print("Make sure the mock API server is still running on port 8000.")


# ============================================================================
# STEP 6: Programmatic Examples
# ============================================================================

def run_example_queries():
    """
    Run a few example queries to demonstrate the agent's capabilities.

    This is useful for automated testing.
    """

    print("=" * 70)
    print("  SIMPLE AI AGENT - EXAMPLE QUERIES (CLAUDE API)")
    print("=" * 70)

    # Initialize the agent
    llm = create_claude_llm()
    system_prompt = get_system_prompt()
    agent = SimpleAgent(llm, system_prompt)

    # Define test queries
    test_queries = [
        "What is an AI agent in the context of LLMs?",
        "Explain the Observe-Think-Act loop in 3 short sentences.",
        "What makes Claude well-suited for building AI agents?",
    ]

    # Run each query and display results
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*70}")
        print(f"Query {i}: {query}")
        print('-' * 70)

        # Get agent's response
        try:
            response = agent.run(query)
            # Handle potential encoding issues on Windows
            try:
                print(f"Response:\n{response}")
            except UnicodeEncodeError:
                # Fallback: encode with error handling for Windows console
                safe_response = response.encode('ascii', errors='replace').decode('ascii')
                print(f"Response:\n{safe_response}")
        except Exception as e:
            print(f"[-] Error: {e}")


# ============================================================================
# STEP 7: Main Entry Point
# ============================================================================

def main():
    """
    Main entry point for the script.

    Choose:
    - 1: Interactive chat
    - 2: Example queries
    """

    # Choose which demo to run
    mode = input("Choose mode:\n1. Interactive chat\n2. Example queries\nEnter 1 or 2: ").strip()

    if mode == "1":
        run_interactive_demo()
    elif mode == "2":
        run_example_queries()
    else:
        print("Invalid choice. Running interactive mode by default.")
        run_interactive_demo()


# ============================================================================
# Script Execution
# ============================================================================

if __name__ == "__main__":
    main()
