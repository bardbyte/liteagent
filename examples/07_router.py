"""
Example 7: Router (Multi-Agent)
================================

Route user messages to the right specialist agent based on intent.
Each agent has scoped tools and a focused system prompt.

Use this when you need:
- A single entry point that handles different types of questions
- Specialist agents that are each great at one thing
- To keep tool counts low per agent (better accuracy)

Setup:
    pip install -e .
    # Make sure .env has CONFIG_PATH set (see setup.sh)
"""

import asyncio
from liteagent import Agent, Router


# --- Define specialist agents ---

analyst = Agent(
    system_prompt=(
        "You answer data questions using Looker's conversational analytics. "
        "For direct data questions, use the conversational-analytics tool. "
        "For more complex queries, use query or query-sql."
    ),
    tools=["conversational-analytics", "query", "query-sql"],
)

explorer = Agent(
    system_prompt=(
        "You help users discover what data is available in Looker. "
        "List models, explores, dimensions, and measures. "
        "Explain what each field means in business terms."
    ),
    tools=["get-models", "get-explores", "get-dimensions", "get-measures"],
)

content_viewer = Agent(
    system_prompt=(
        "You help users find and view saved Looker content — "
        "dashboards and looks. List what's available and run them on request."
    ),
    tools=["get-looks", "run-look", "get-dashboards", "run-dashboard"],
)

general = Agent(
    system_prompt=(
        "You are a helpful Looker assistant. For data questions, suggest "
        "the user ask about specific metrics. For schema questions, suggest "
        "they ask what data is available."
    ),
)


# --- Define routing logic ---

def route(message: str) -> str:
    """Route based on keywords in the message."""
    msg = message.lower()

    # Schema / discovery questions
    if any(w in msg for w in [
        "model", "explore", "dimension", "measure", "field",
        "schema", "available", "what data", "what can i",
    ]):
        return "explorer"

    # Saved content questions
    if any(w in msg for w in [
        "dashboard", "look", "saved", "report", "existing",
    ]):
        return "content"

    # Data questions (numbers, metrics, aggregations)
    if any(w in msg for w in [
        "revenue", "sales", "total", "count", "average", "sum",
        "how many", "how much", "top", "bottom", "by region",
        "by month", "by category", "trend", "compare",
    ]):
        return "analyst"

    return "general"


# --- Create router ---

router = Router(
    agents={
        "analyst": analyst,
        "explorer": explorer,
        "content": content_viewer,
        "general": general,
    },
    route=route,
    default="general",
)


async def main():
    questions = [
        "What models are available?",           # → explorer
        "Show me total revenue by region",       # → analyst
        "What saved dashboards do we have?",     # → content
        "How do I use Looker?",                  # → general
        "What dimensions are in the orders explore?",  # → explorer
        "Top 10 customers by spend",             # → analyst
    ]

    for q in questions:
        agent_name = route(q)
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"Routed to: {agent_name}")
        print(f"{'='*60}")

        result = await router.run(q)
        print(f"Answer: {result.content[:200]}...")
        print(f"Tools used: {result.tools_used}")


if __name__ == "__main__":
    asyncio.run(main())
