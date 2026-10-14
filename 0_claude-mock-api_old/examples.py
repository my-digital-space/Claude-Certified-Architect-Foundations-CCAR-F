"""
Example integrations showing how to use the Claude Mock API
as a drop-in replacement for various AI frameworks.

Make sure the server is running first:
    start-server.bat  (or: uvicorn app.main:app --reload)
"""

# ─────────────────────────────────────────────────────────────────────
# Example 1: LangChain ChatOpenAI (Most Common)
# ─────────────────────────────────────────────────────────────────────

def example_langchain_chat():
    """Basic LangChain ChatOpenAI usage with our mock server."""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    # Point to our local mock server
    llm = ChatOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="mock-api-key-change-me",
        model="claude"
    )

    # Single-turn chat
    response = llm.invoke([
        SystemMessage(content="You are a Python expert."),
        HumanMessage(content="Write a function to calculate factorial.")
    ])

    print("LangChain Response:")
    print(response.content)


# ─────────────────────────────────────────────────────────────────────
# Example 2: LangChain with Streaming
# ─────────────────────────────────────────────────────────────────────

def example_langchain_streaming():
    """Stream tokens as they arrive."""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage

    llm = ChatOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="mock-api-key-change-me",
        model="claude",
        streaming=True
    )

    print("\nStreaming Response:")
    for chunk in llm.stream([HumanMessage(content="Count from 1 to 10")]):
        print(chunk.content, end="", flush=True)
    print()


# ─────────────────────────────────────────────────────────────────────
# Example 3: OpenAI Python SDK
# ─────────────────────────────────────────────────────────────────────

def example_openai_sdk():
    """Native OpenAI SDK pointing at our mock server."""
    from openai import OpenAI

    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="mock-api-key-change-me"
    )

    # Blocking completion
    response = client.chat.completions.create(
        model="claude",
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "What is FastAPI?"}
        ]
    )

    print("\nOpenAI SDK Response:")
    print(response.choices[0].message.content)


# ─────────────────────────────────────────────────────────────────────
# Example 4: Multi-turn Conversation
# ─────────────────────────────────────────────────────────────────────

def example_multi_turn():
    """Demonstrate multi-turn conversation with context."""
    from openai import OpenAI

    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="mock-api-key-change-me"
    )

    messages = [
        {"role": "system", "content": "You are a helpful math tutor."},
        {"role": "user", "content": "What is 15 + 27?"},
    ]

    # First turn
    response = client.chat.completions.create(model="claude", messages=messages)
    assistant_reply = response.choices[0].message.content
    messages.append({"role": "assistant", "content": assistant_reply})

    print("\nMulti-turn Conversation:")
    print(f"Assistant: {assistant_reply}")

    # Second turn (with context)
    messages.append({"role": "user", "content": "Now multiply that by 2."})
    response = client.chat.completions.create(model="claude", messages=messages)
    print(f"Assistant: {response.choices[0].message.content}")


# ─────────────────────────────────────────────────────────────────────
# Example 5: How to Switch to Real OpenAI Later
# ─────────────────────────────────────────────────────────────────────

def example_production_switch():
    """
    Switching from mock to real OpenAI requires NO code changes.
    Just update the constructor arguments.
    """
    from langchain_openai import ChatOpenAI

    # DEVELOPMENT (using our mock Claude server)
    llm_dev = ChatOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="mock-api-key-change-me",
        model="claude"
    )

    # PRODUCTION (using real OpenAI)
    llm_prod = ChatOpenAI(
        # No base_url needed -> defaults to https://api.openai.com/v1
        api_key="sk-proj-your-real-openai-key",
        model="gpt-4o"
    )

    # Same interface, zero logic changes
    # response = llm_dev.invoke([...])   # During local dev
    # response = llm_prod.invoke([...])  # In production

    print("\n✅ Production Switch Example: No code changes needed!")


# ─────────────────────────────────────────────────────────────────────
# Run Examples
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("Claude Mock API - Integration Examples")
    print("=" * 70)

    try:
        example_langchain_chat()
        example_langchain_streaming()
        example_openai_sdk()
        example_multi_turn()
        example_production_switch()

        print("\n" + "=" * 70)
        print("✅ All examples completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. The server is running: start-server.bat")
        print("  2. Dependencies are installed: pip install langchain-openai openai")
