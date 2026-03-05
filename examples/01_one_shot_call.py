"""
Example 1: One-Shot LLM Call
=============================

The simplest thing you can do — send a prompt, get a response.
No tools, no ReAct loop, no conversation history.

Use this when you need:
- A quick LLM response (summarization, classification, extraction)
- To process data through the LLM without tool access
- A building block inside a larger Python script

Setup:
    pip install -e .
    # Make sure .env has CONFIG_PATH set (see setup.sh)
"""

import asyncio
from liteagent import call, call_sync


async def main():
    # --- Basic call ---
    result = await call("What is the capital of France?")
    print(f"Answer: {result}")
    # Result has __str__, so print() just works

    # --- With a system prompt ---
    result = await call(
        "Summarize the key metrics a retail analyst tracks daily",
        system="You are a senior data analyst at a Fortune 500 company.",
    )
    print(f"\nSummary:\n{result.content}")

    # --- Override model ---
    result = await call(
        "Explain LookML in one sentence",
        model="gemini-2.0-flash",
    )
    print(f"\nLookML: {result}")

    # --- Check result metadata ---
    print(f"\nIterations: {result.iterations}")  # always 1 for call()
    print(f"Has content: {bool(result)}")


# --- Sync version (for scripts, Streamlit, Jupyter) ---
def sync_example():
    result = call_sync(
        "List 3 common Looker dimension types",
        system="You are a Looker expert. Be concise.",
    )
    print(f"\nSync result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
    sync_example()
