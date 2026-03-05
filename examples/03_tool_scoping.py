"""
Example 3: Tool Scoping
========================

Restrict which MCP tools an agent can see. This is CRITICAL for
multi-agent systems where each agent has a specific job.

Without scoping: the LLM sees 40+ tools and sometimes picks the wrong one.
With scoping: the LLM sees only what it needs → more accurate, faster.

Use this when you need:
- Agents with specific responsibilities
- To prevent an agent from calling dangerous tools (delete, create)
- To build multi-agent systems where each agent is a specialist

Setup:
    pip install -e .
    # Make sure .env has CONFIG_PATH set (see setup.sh)
"""

import asyncio
from liteagent import Agent


async def main():
    # --- Conversational analytics specialist ---
    # Only gets the one-shot CA tool — can't manually explore schemas
    ca_agent = Agent(
        system_prompt=(
            "You answer data questions using the conversational-analytics tool. "
            "Pass the user's question directly to the tool."
        ),
        tools=["conversational-analytics"],
    )

    result = await ca_agent.run("What is total revenue by region?")
    print(f"CA Agent: {result.content[:200]}")
    print(f"Tools available: {ca_agent.tool_names}")

    # --- Schema explorer ---
    # Can discover models and fields, but CANNOT run queries
    explorer = Agent(
        system_prompt=(
            "You help users understand what data is available in Looker. "
            "List models, explores, dimensions, and measures. "
            "You do NOT run queries — just describe the schema."
        ),
        tools=["get-models", "get-explores", "get-dimensions", "get-measures"],
    )

    result = await explorer.run("What data is available?")
    print(f"\nExplorer: {result.content[:200]}")
    print(f"Tools available: {explorer.tool_names}")

    # --- Query runner ---
    # Can run queries but not modify anything
    querier = Agent(
        system_prompt=(
            "You run Looker queries. You receive a fully specified query "
            "(model, explore, fields) and execute it."
        ),
        tools=["query", "query-sql", "query-url"],
    )

    result = await querier.run(
        "Run a query on model 'ecommerce', explore 'order_items', "
        "dimensions ['products.category'], measures ['order_items.total_revenue']"
    )
    print(f"\nQuerier: {result.content[:200]}")

    # --- Read-only content viewer ---
    # Can view saved looks and dashboards, but not create or modify
    viewer = Agent(
        system_prompt="You help users find and view saved Looker content.",
        tools=["get-looks", "run-look", "get-dashboards", "run-dashboard"],
    )

    result = await viewer.run("What saved dashboards are available?")
    print(f"\nViewer: {result.content[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
