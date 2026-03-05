"""
Example 10: Google ADK Integration
====================================

Use liteagent's ReAct loop as an agent inside Google ADK's
multi-agent orchestration framework.

Your SafeChain+MCP ReAct agent becomes a node in ADK pipelines,
gaining: adk web UI, Cloud Run deployment, session persistence,
and agent-to-agent transfer — for free.

Use this when you need:
- To deploy agents to Cloud Run or Vertex AI Agent Engine
- ADK's built-in dev UI (adk web)
- LLM-driven agent routing (ADK's transfer_to_agent)
- To combine your MCP agents with other ADK agents

Setup:
    pip install -e ".[adk]"   # installs google-adk
    # Make sure .env has CONFIG_PATH set (see setup.sh)

Run with ADK dev UI:
    adk web
"""

# --- Pattern 1: LiteAgent in an ADK Sequential Pipeline ---

def sequential_pipeline_example():
    """
    Three-step pipeline: Plan → Query → Summarize.
    LiteAgent handles the Looker query step.
    """
    from liteagent import LiteAgent

    try:
        from google.adk.agents import SequentialAgent, LlmAgent
        from google.adk.runners import InMemoryRunner
        from google.genai import types as genai_types
    except ImportError:
        print("google-adk not installed. Run: pip install google-adk")
        return

    # Your SafeChain ReAct agent, wrapped for ADK
    looker_agent = LiteAgent(
        name="LookerAnalyst",
        description="Queries Looker's semantic layer via MCP tools",
        system_prompt=(
            "You are a Looker analytics expert. Query the data the user "
            "asks about and return raw results with the generated SQL."
        ),
        tool_names=["conversational-analytics", "query", "query-sql"],
        output_key="query_result",
    )

    # ADK native agents for planning and summarizing
    planner = LlmAgent(
        name="QueryPlanner",
        model="gemini-2.5-flash",
        instruction=(
            "You plan data queries. The user will ask a business question. "
            "Rephrase it as a specific, unambiguous data query that can be "
            "run against Looker. Output just the refined query."
        ),
        output_key="planned_query",
    )

    summarizer = LlmAgent(
        name="Summarizer",
        model="gemini-2.5-flash",
        instruction=(
            "You write executive summaries. You receive raw query results "
            "in {query_result}. Write a 3-sentence summary: key finding, "
            "supporting data, and recommended action."
        ),
    )

    # Chain them
    pipeline = SequentialAgent(
        name="AnalyticsPipeline",
        sub_agents=[planner, looker_agent, summarizer],
    )

    # Run
    runner = InMemoryRunner(agent=pipeline)
    user_msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text="How did Q4 revenue compare to Q3 by region?")],
    )

    print("Running Sequential Pipeline...")
    for event in runner.run(
        user_id="analyst_1", session_id="session_1", new_message=user_msg
    ):
        if event.content and event.content.parts:
            author = event.author or "system"
            text = event.content.parts[0].text
            print(f"[{author}] {text[:200]}")

    print("\nDone!")


# --- Pattern 2: LiteAgent with LLM-driven routing ---

def router_example():
    """
    ADK's LLM picks which specialist agent handles the question.
    No manual routing function needed — the LLM decides.
    """
    from liteagent import LiteAgent

    try:
        from google.adk.agents import LlmAgent
        from google.adk.runners import InMemoryRunner
        from google.genai import types as genai_types
    except ImportError:
        print("google-adk not installed. Run: pip install google-adk")
        return

    # Specialist agents
    data_agent = LiteAgent(
        name="DataAnalyst",
        description="Answers data questions by querying Looker (revenue, sales, counts, metrics)",
        system_prompt="You answer data questions using Looker tools.",
        tool_names=["conversational-analytics", "query"],
        output_key="data_result",
    )

    schema_agent = LiteAgent(
        name="SchemaExplorer",
        description="Explains what data is available in Looker (models, explores, fields)",
        system_prompt="You help users discover Looker schemas.",
        tool_names=["get-models", "get-explores", "get-dimensions", "get-measures"],
        output_key="schema_result",
    )

    # Coordinator — the LLM reads sub_agent descriptions and routes
    coordinator = LlmAgent(
        name="Coordinator",
        model="gemini-2.5-flash",
        instruction=(
            "You are a data team coordinator. Route questions to the right specialist:\n"
            "- DataAnalyst: for questions about numbers, metrics, revenue, trends\n"
            "- SchemaExplorer: for questions about what data/fields/models exist\n"
            "Transfer to the right agent. Do not answer directly."
        ),
        sub_agents=[data_agent, schema_agent],
    )

    runner = InMemoryRunner(agent=coordinator)

    questions = [
        "What models are available?",
        "Show me total revenue by region",
        "What dimensions does the orders explore have?",
    ]

    for q in questions:
        print(f"\n{'='*50}")
        print(f"Q: {q}")
        user_msg = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=q)],
        )
        for event in runner.run(
            user_id="user_1", session_id=f"s_{hash(q)}", new_message=user_msg
        ):
            if event.content and event.content.parts:
                print(f"[{event.author}] {event.content.parts[0].text[:150]}")


# --- Pattern 3: LiteAgent as a tool inside another agent ---

def agent_as_tool_example():
    """
    Wrap a LiteAgent as a callable tool for another ADK agent.
    The outer agent decides when to invoke your Looker agent.
    """
    from liteagent import LiteAgent

    try:
        from google.adk.agents import LlmAgent
        from google.adk.tools import agent_tool
        from google.adk.runners import InMemoryRunner
        from google.genai import types as genai_types
    except ImportError:
        print("google-adk not installed. Run: pip install google-adk")
        return

    looker = LiteAgent(
        name="LookerTool",
        description="Queries Looker for data",
        system_prompt="You run Looker queries and return results.",
        tool_names=["conversational-analytics", "query"],
    )

    # Wrap as a tool
    looker_tool = agent_tool.AgentTool(agent=looker)

    # Outer agent uses it like any other tool
    report_writer = LlmAgent(
        name="ReportWriter",
        model="gemini-2.5-flash",
        instruction=(
            "You write data-driven reports. When you need data, use the "
            "LookerTool to query it. Then format the results into a "
            "professional report with sections, tables, and insights."
        ),
        tools=[looker_tool],
    )

    runner = InMemoryRunner(agent=report_writer)
    user_msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text="Write a report on Q4 sales performance")],
    )

    print("Running Report Writer with Looker tool...")
    for event in runner.run(
        user_id="user_1", session_id="report_1", new_message=user_msg
    ):
        if event.content and event.content.parts:
            print(f"[{event.author}] {event.content.parts[0].text[:200]}")


if __name__ == "__main__":
    import sys

    if "--router" in sys.argv:
        router_example()
    elif "--tool" in sys.argv:
        agent_as_tool_example()
    else:
        sequential_pipeline_example()
