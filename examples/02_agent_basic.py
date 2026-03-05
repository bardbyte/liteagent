"""
Example 2: Basic Agent (ReAct Loop)
====================================

Create an agent with a system prompt. It gets ALL MCP tools and can
call them autonomously in a ReAct loop until it has an answer.

Use this when you need:
- An agent that can call tools (Looker queries, schema discovery, etc.)
- Multi-step reasoning (discover schema → pick fields → query → present)
- A programmatic agent in a script or service

Setup:
    pip install -e .
    # Make sure .env has CONFIG_PATH set (see setup.sh)
"""

import asyncio
from liteagent import Agent, ConsoleCallback


async def main():
    # --- Basic agent with all tools ---
    agent = Agent(
        system_prompt="You are a Looker analytics expert. Answer data questions clearly.",
    )

    result = await agent.run("What Looker models are available?")

    print(f"\nAnswer: {result.content}")
    print(f"Tools used: {result.tools_used}")
    print(f"Iterations: {result.iterations}")

    # --- With thinking visualization ---
    agent = Agent(
        system_prompt="You are a Looker analytics expert.",
        on_thinking=ConsoleCallback(),  # rich console panels
    )

    result = await agent.run("Show me the explores in the first model you find")

    # --- With a plain function callback ---
    agent = Agent(
        system_prompt="You are a Looker analytics expert.",
        on_thinking=lambda e: print(f"  [{e.type.value}] {e.content[:100]}"),
    )

    result = await agent.run("What dimensions are available for customer data?")

    # --- Inspect tool calls ---
    for tc in result.tool_calls:
        status = "OK" if tc.ok else f"ERROR: {tc.error}"
        print(f"  {tc.name}: {status}")

    if result.has_errors:
        print(f"\nFailed tools: {[tc.name for tc in result.failed_tools]}")

    # --- Sync version ---
    agent = Agent(system_prompt="You are a Looker expert.")
    result = agent.run_sync("How many models are available?")
    print(f"\nSync: {result}")


if __name__ == "__main__":
    asyncio.run(main())
