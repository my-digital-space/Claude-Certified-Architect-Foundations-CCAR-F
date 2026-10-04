"""
A simple AI agent that demonstrates the basic usage of Claude / Anthropic API style:
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

# Load environment variables from .env file if it exists
# With override=True, the .env values replace the existing OS values
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

# Test the above LLM call once
# if __name__ == "__main__":
#     # Create the LLM connection.
#     llm = create_claude_llm()

#     # Make one test request.
#     user_input = input("\nYou: ").strip()
#     response = llm.invoke(user_input)

#     # Print only Claude's generated text.
#     print(response.content)



# ============================================================================
# STEP 3: Create Tools
# ============================================================================

import logging

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool


# ----------------------------------------------------------------------------
# Configure logging
# ----------------------------------------------------------------------------
# We are logging observable agent behavior:
#
#   - Agent iteration
#   - stop_reason
#   - tool requested by Claude
#   - arguments supplied by Claude
#   - tool execution result
#
# We are NOT trying to print hidden chain-of-thought.
# The goal is to understand the agent control flow.
# ----------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("simple-agent")


# ============================================================================
# TOOL 1: Get Product Price
# ============================================================================

@tool
def get_product_price(product_name: str) -> float:
    """
    Return the base price of a product.

    In a real application this could query a database or REST API.
    For learning, we simply return a fixed value.
    """

    logger.info(
        "Executing tool: get_product_price(product_name='%s')",
        product_name
    )

    # Simple hard-coded product catalog for learning purposes.
    products = {
        "laptop": 1000.00,
        "monitor": 500.00,
        "keyboard": 100.00,
    }

    price = products.get(product_name.lower())

    if price is None:
        raise ValueError(
            f"Product '{product_name}' was not found."
        )

    logger.info(
        "Tool result: get_product_price -> %.2f",
        price
    )

    return price


# ============================================================================
# TOOL 2: Apply Customer Discount
# ============================================================================

@tool
def apply_discount(base_price: float, customer_type: str) -> float:
    """
    Apply a discount based on the customer type.

    IMPORTANT:
    This tool depends on the output from Tool 1.

    Claude cannot know the correct base_price until Tool 1
    has already been executed.
    """

    logger.info(
        "Executing tool: apply_discount(base_price=%.2f, customer_type='%s')",
        base_price,
        customer_type
    )

    discounts = {
        "regular": 0.00,
        "silver": 0.10,
        "gold": 0.20,
    }

    discount_percentage = discounts.get(
        customer_type.lower(),
        0.00
    )

    discounted_price = (
        base_price * (1 - discount_percentage)
    )

    logger.info(
        "Discount applied: %.0f%%",
        discount_percentage * 100
    )

    logger.info(
        "Tool result: apply_discount -> %.2f",
        discounted_price
    )

    return discounted_price


# ============================================================================
# TOOL 3: Calculate Tax
# ============================================================================

@tool
def calculate_tax(price_after_discount: float, state: str) -> float:
    """
    Calculate tax on the discounted price.

    This tool depends on the result of Tool 2.
    """

    logger.info(
        "Executing tool: calculate_tax(price_after_discount=%.2f, state='%s')",
        price_after_discount,
        state
    )

    # Simple tax table for learning.
    tax_rates = {
        "CA": 0.10,
        "NY": 0.085,
        "TX": 0.0825,
    }

    tax_rate = tax_rates.get(
        state.upper(),
        0.05
    )

    tax = price_after_discount * tax_rate

    logger.info(
        "Tax rate: %.2f%%",
        tax_rate * 100
    )

    logger.info(
        "Tool result: calculate_tax -> %.2f",
        tax
    )

    return tax


# ============================================================================
# STEP 4: Create the Agentic Loop
# ============================================================================

def run_agent(user_input: str):
    """
    Run our manual agentic loop.

    The Python code controls the loop.

    Claude:
        1. Receives the conversation.
        2. Decides whether a tool is required.
        3. Returns either:
              stop_reason = "tool_use"
           or:
              stop_reason = "end_turn"

    Our Python code:
        4. Executes requested tools.
        5. Adds the tool results to conversation history.
        6. Sends the updated history to Claude.
        7. Repeats until Claude returns "end_turn".
    """

    # ------------------------------------------------------------------------
    # Create Claude LLM using our existing STEP 2 function.
    # ------------------------------------------------------------------------

    llm = create_claude_llm()

    # ------------------------------------------------------------------------
    # Make all tools available to Claude.
    # ------------------------------------------------------------------------

    tools = [
        get_product_price,
        apply_discount,
        calculate_tax,
    ]

    llm_with_tools = llm.bind_tools(tools)

    # ------------------------------------------------------------------------
    # Conversation history.
    #
    # This list is the "memory" of our current agent execution.
    #
    # It will eventually contain:
    #
    #   HumanMessage
    #   AIMessage
    #   ToolMessage
    #   AIMessage
    #   ToolMessage
    #   ...
    # ------------------------------------------------------------------------

    messages = [
        HumanMessage(content=user_input)
    ]

    # ------------------------------------------------------------------------
    # Prevent an accidental infinite loop.
    # ------------------------------------------------------------------------

    max_iterations = 10

    for iteration in range(1, max_iterations + 1):

        logger.info("")
        logger.info(
            "============================================================"
        )
        logger.info(
            "AGENT ITERATION %d",
            iteration
        )
        logger.info(
            "============================================================"
        )

        # ====================================================================
        # STEP 4.1
        # Send conversation history to Claude
        # ====================================================================

        logger.info(
            "Sending conversation history to Claude..."
        )

        response = llm_with_tools.invoke(messages)

        # --------------------------------------------------------------------
        # IMPORTANT:
        #
        # Add Claude's response to the history BEFORE we execute its tools.
        # --------------------------------------------------------------------

        messages.append(response)

        # ====================================================================
        # STEP 4.2
        # Inspect stop_reason
        # ====================================================================

        stop_reason = response.response_metadata.get(
            "stop_reason"
        )

        logger.info(
            "Claude stop_reason = %s",
            stop_reason
        )

        # --------------------------------------------------------------------
        # Print the observable content returned by Claude.
        #
        # We are not printing hidden chain-of-thought.
        # We are only displaying the actual returned message/tool information.
        # --------------------------------------------------------------------

        logger.info(
            "Claude response content = %s",
            response.content
        )

        # ====================================================================
        # CASE 1: Claude wants to use tools
        # ====================================================================

        if stop_reason == "tool_use":

            logger.info(
                "Claude wants to use tool(s)."
            )

            # ----------------------------------------------------------------
            # LangChain exposes tool calls through response.tool_calls.
            # ----------------------------------------------------------------

            tool_calls = response.tool_calls

            logger.info(
                "Number of requested tool calls = %d",
                len(tool_calls)
            )

            # ----------------------------------------------------------------
            # Execute each requested tool.
            # ----------------------------------------------------------------

            for tool_call in tool_calls:

                tool_name = tool_call["name"]

                tool_args = tool_call["args"]

                tool_call_id = tool_call["id"]

                logger.info(
                    "------------------------------------------------------------"
                )

                logger.info(
                    "Claude requested tool: %s",
                    tool_name
                )

                logger.info(
                    "Tool arguments: %s",
                    tool_args
                )

                # ------------------------------------------------------------
                # Execute the appropriate Python tool.
                #
                # We intentionally use simple if/elif logic here because
                # we are learning the agentic loop.
                #
                # Later we can replace this with a tool registry.
                # ------------------------------------------------------------

                if tool_name == "get_product_price":

                    tool_result = get_product_price.invoke(
                        tool_args
                    )

                elif tool_name == "apply_discount":

                    tool_result = apply_discount.invoke(
                        tool_args
                    )

                elif tool_name == "calculate_tax":

                    tool_result = calculate_tax.invoke(
                        tool_args
                    )

                else:

                    raise ValueError(
                        f"Unknown tool requested: {tool_name}"
                    )

                # ------------------------------------------------------------
                # CRITICAL STEP
                #
                # Add the tool result to the conversation history.
                #
                # Claude MUST see this result on the next iteration.
                # ------------------------------------------------------------

                messages.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call_id
                    )
                )

                logger.info(
                    "Tool result appended to conversation history: %s",
                    tool_result
                )

            # ----------------------------------------------------------------
            # Continue the loop.
            #
            # The next iteration sends the updated conversation to Claude.
            # ----------------------------------------------------------------

            continue

        # ====================================================================
        # CASE 2: Claude has finished
        # ====================================================================

        elif stop_reason == "end_turn":

            logger.info(
                "Claude returned end_turn."
            )

            logger.info(
                "Agentic loop completed."
            )

            return response.content

        # ====================================================================
        # CASE 3: Unexpected stop reason
        # ====================================================================

        else:

            logger.warning(
                "Unexpected stop_reason received: %s",
                stop_reason
            )

            return response.content

    # ------------------------------------------------------------------------
    # Safety mechanism in case Claude keeps requesting tools forever.
    # ------------------------------------------------------------------------

    raise RuntimeError(
        f"Agent exceeded maximum iterations: {max_iterations}"
    )


# ============================================================================
# STEP 5: Test the Agent
# ============================================================================

if __name__ == "__main__":

    # ------------------------------------------------------------------------
    # This request intentionally requires several dependent steps.
    #
    # Claude should:
    #
    #   1. Find the laptop price.
    #   2. Apply the Gold customer discount.
    #   3. Calculate California tax.
    #   4. Give us the final answer.
    #
    # Each later calculation depends on information returned by
    # the previous tool.
    # ------------------------------------------------------------------------

    user_question = (
        "What is the final price of a laptop for a Gold customer "
        "in California?"
    )

    final_answer = run_agent(user_question)

    print("")
    print("============================================================")
    print("FINAL ANSWER")
    print("============================================================")
    print(final_answer)

