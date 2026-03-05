"""
Example 6: Streaming
=====================

Get thinking events as they happen, instead of waiting for the full result.
Useful for real-time UIs, progress bars, or logging.

Use this when you need:
- To show users what the agent is doing in real time
- To log agent behavior for debugging
- To build progress indicators in UIs
- To stream to a websocket or SSE endpoint

Setup:
    pip install -e .
    # Make sure .env has CONFIG_PATH set (see setup.sh)
"""

import asyncio
from liteagent import Agent, ThinkingType


async def main():
    agent = Agent(
        system_prompt="You are a Looker analytics expert.",
        tools=["conversational-analytics", "get-models", "get-explores"],
    )

    # --- Stream events ---
    print("Streaming agent thinking:\n")

    async for event in agent.stream("What models are available and what can I query?"):
        if event.type == ThinkingType.TOOL_CALL:
            print(f"  -> Calling tool: {event.metadata.get('tool_name', '?')}")

        elif event.type == ThinkingType.TOOL_RESULT:
            preview = event.content[:80].replace("\n", " ")
            print(f"  <- Result: {preview}...")

        elif event.type == ThinkingType.REASONING:
            preview = event.content[:100].replace("\n", " ")
            print(f"  [thinking] {preview}...")

        elif event.type == ThinkingType.FINAL_ANSWER:
            print(f"\n{'='*60}")
            print(f"ANSWER:\n{event.content}")
            print(f"{'='*60}")

        elif event.type == ThinkingType.ERROR:
            print(f"  !! Error: {event.content}")


    # --- Collect events for logging ---
    print("\n\nCollecting events for logging:\n")

    events = []
    async for event in agent.stream("Show me total revenue"):
        events.append(event)

    print(f"Total events: {len(events)}")
    for i, e in enumerate(events):
        print(f"  {i+1}. [{e.type.value}] {e.content[:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
