"""
Example 9: Interactive Chat
=============================

Launch a CLI chat session with conversation memory.
Supports /tools, /clear, /help, /quit commands.

Use this when you need:
- An interactive exploration session with Looker
- To test prompts and tool behavior conversationally
- A quick way to query data without writing code

Setup:
    pip install -e .
    # Make sure .env has CONFIG_PATH set (see setup.sh)

Run:
    python examples/09_chat.py

    # Or with the CLI command:
    liteagent --system "You are a Looker analytics expert"

    # With tool scoping:
    liteagent --tools conversational-analytics get-models get-explores
"""

import asyncio
from liteagent import Chat, ConsoleCallback


async def main():
    # --- Basic chat ---
    chat = Chat(
        system_prompt=(
            "You are a Looker analytics expert. You help users explore data "
            "by querying Looker's semantic layer. Always show the SQL that was "
            "generated. Present data in tables when possible."
        ),
        on_thinking=ConsoleCallback(),
    )

    await chat.start()


async def scoped_chat():
    """Chat with only conversational analytics tool."""
    chat = Chat(
        system_prompt=(
            "You answer data questions using Looker's conversational analytics. "
            "Pass questions directly to the tool and present the results clearly."
        ),
        tools=["conversational-analytics"],
        on_thinking=ConsoleCallback(),
    )

    await chat.start()


async def programmatic_chat():
    """Use Chat programmatically (not interactively)."""
    chat = Chat(
        system_prompt="You are a data analyst.",
        tools=["get-models", "get-explores"],
    )

    # Send messages programmatically
    r1 = await chat.send("What models are available?")
    print(f"Models: {r1.content[:200]}")

    # Follow-up uses conversation history
    r2 = await chat.send("Tell me more about the first one")
    print(f"Details: {r2.content[:200]}")

    # Check history
    print(f"\nHistory length: {len(chat.history)} messages")

    # Clear and start fresh
    chat.clear()
    print(f"After clear: {len(chat.history)} messages")


if __name__ == "__main__":
    # Pick which mode to run:
    import sys

    if "--programmatic" in sys.argv:
        asyncio.run(programmatic_chat())
    elif "--scoped" in sys.argv:
        asyncio.run(scoped_chat())
    else:
        asyncio.run(main())
