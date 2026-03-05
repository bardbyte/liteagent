"""
Example 5: Guardrails
======================

Validate inputs and outputs before/after LLM calls.
Guardrails are plain functions: return None to allow, or a string to block.

Use this when you need:
- To prevent destructive operations (delete, drop, create)
- To block PII from leaking in responses
- To enforce query boundaries (only certain models/explores)
- To add compliance checks to agent behavior

Setup:
    pip install -e .
    # Make sure .env has CONFIG_PATH set (see setup.sh)
"""

import re
import asyncio
from liteagent import Agent, GuardrailError


# --- Input guardrails (validate what the user asks) ---

def block_destructive(prompt: str) -> str | None:
    """Block any request that sounds destructive."""
    dangerous = ["delete", "drop", "destroy", "remove", "truncate", "create", "modify"]
    for word in dangerous:
        if word in prompt.lower():
            return f"Blocked: '{word}' operations are not allowed through this agent."
    return None


def require_question(prompt: str) -> str | None:
    """Only allow questions, not commands."""
    if len(prompt.strip()) < 5:
        return "Please provide a complete question."
    return None


def scope_to_analytics(prompt: str) -> str | None:
    """Only allow analytics-related questions."""
    off_topic = ["weather", "stock price", "joke", "recipe", "news"]
    for topic in off_topic:
        if topic in prompt.lower():
            return f"This agent only handles data analytics questions, not '{topic}'."
    return None


# --- Output guardrails (validate what the LLM returns) ---

def no_pii_in_output(content: str) -> str | None:
    """Block responses that contain SSN, credit card, or email patterns."""
    patterns = {
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "Credit Card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    }
    for name, pattern in patterns.items():
        if re.search(pattern, content):
            return f"Response blocked: contains potential {name} data."
    return None


def max_length(content: str) -> str | None:
    """Keep responses under 5000 chars."""
    if len(content) > 5000:
        return "Response too long. Please ask a more specific question."
    return None


async def main():
    # --- Agent with all guardrails ---
    agent = Agent(
        system_prompt="You are a Looker analytics expert.",
        tools=["conversational-analytics", "get-models", "get-explores"],
        input_guardrails=[block_destructive, require_question, scope_to_analytics],
        output_guardrails=[no_pii_in_output, max_length],
    )

    # This works fine
    result = await agent.run("What models are available in Looker?")
    print(f"OK: {result.content[:100]}")

    # This gets blocked by input guardrail
    try:
        await agent.run("Delete all dashboards")
    except GuardrailError as e:
        print(f"\nBlocked: {e}")
        print(f"Guardrail: {e.guardrail_name}")

    # This gets blocked by scope guardrail
    try:
        await agent.run("What's the weather today?")
    except GuardrailError as e:
        print(f"\nBlocked: {e}")

    # This gets blocked by input length guardrail
    try:
        await agent.run("hi")
    except GuardrailError as e:
        print(f"\nBlocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
