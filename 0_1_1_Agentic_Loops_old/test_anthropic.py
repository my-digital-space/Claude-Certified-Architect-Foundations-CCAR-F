"""
Test LangChain ChatAnthropic with our mock API server.
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# Initialize ChatAnthropic pointing to our mock API server
llm = ChatAnthropic(
    anthropic_api_url="http://localhost:8000",
    anthropic_api_key="mock-api-key-001",
    model_name="claude-3-5-sonnet-20241022",
    temperature=0.7,
)

print("Sending request via ChatAnthropic...")
response = llm.invoke([
    SystemMessage(content="You are a helpful coding assistant."),
    HumanMessage(content="What are the three main paradigms of programming? Answer in 3 bullet points.")
])

print("\n--- Response ---")
print(response.content)
