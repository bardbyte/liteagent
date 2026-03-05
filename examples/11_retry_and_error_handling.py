"""
Example 11: Retry and Error Handling
======================================

Handle tool failures gracefully with automatic retries
and detailed error inspection.

Use this when you need:
- Resilient agents that survive intermittent MCP server errors
- To understand why a query failed
- To build monitoring/alerting around agent health

Setup:
    pip install -e .
    # Make sure .env has CONFIG_PATH set (see setup.sh)
"""

import asyncio
from liteagent import Agent, ConsoleCallback


async def main():
    # --- Agent with retries ---
    # If ainvoke() throws, retry up to 2 times before giving up
    agent = Agent(
        system_prompt="You are a Looker analytics expert.",
        tools=["conversational-analytics", "query"],
        max_retries=2,
        on_thinking=ConsoleCallback(),
    )

    result = await agent.run("What is total revenue?")
    print(f"Answer: {result.content[:200]}")

    # --- Inspect errors ---
    if result.has_errors:
        print(f"\nSome tools failed:")
        for tc in result.failed_tools:
            print(f"  {tc.name}: {tc.error}")
    else:
        print(f"\nAll {len(result.tool_calls)} tool calls succeeded")

    # --- Comprehensive result inspection ---
    print(f"\n--- Result Report ---")
    print(f"Content length: {len(result.content)} chars")
    print(f"Iterations: {result.iterations}")
    print(f"Tool calls: {len(result.tool_calls)}")
    print(f"Unique tools: {result.tools_used}")
    print(f"Thinking events: {len(result.thinking)}")
    print(f"Has errors: {result.has_errors}")

    # --- Error handling pattern ---
    try:
        result = await agent.run("Query something that might fail")

        if not result:
            print("Empty response — agent had nothing to say")
        elif result.has_errors:
            print(f"Partial success — some tools failed: {result.failed_tools}")
        else:
            print(f"Full success: {result.content[:100]}")

    except Exception as e:
        print(f"Agent completely failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
