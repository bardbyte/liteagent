"""Interactive chat session with conversation history."""

import argparse
import asyncio
from typing import Callable

from ._agent import Agent
from ._result import Result
from ._thinking import (
    ConsoleCallback, ThinkingCallback, ThinkingEvent, _wrap_callback,
)


class Chat:
    """Interactive chat with conversation memory and CLI commands.

    Example::

        from liteagent import Chat

        chat = Chat(system_prompt="You are a data analyst")
        await chat.start()  # launches interactive CLI
    """

    def __init__(
        self,
        system_prompt: str = "You are a helpful assistant.",
        *,
        model: str | None = None,
        config: str | None = None,
        tools: list[str] | None = None,
        max_iterations: int | None = None,
        history_limit: int | None = None,
        on_thinking: ThinkingCallback | Callable[[ThinkingEvent], None] | None = None,
    ):
        self._agent = Agent(
            system_prompt=system_prompt,
            model=model,
            config=config,
            tools=tools,
            max_iterations=max_iterations,
            on_thinking=on_thinking,
        )
        self._history_limit = history_limit
        self._history: list[dict] = []

    @property
    def history(self) -> list[dict]:
        return list(self._history)

    def clear(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    async def send(self, message: str) -> Result:
        """Send a message and get a response.

        Args:
            message: User message.

        Returns:
            Result from the agent.
        """
        # Run guardrails configured on the underlying agent
        self._agent._check_input_guardrails(message)

        await self._agent._ensure_init()

        limit = self._history_limit
        if limit is None and self._agent._bundle:
            limit = self._agent._bundle.config.history_limit
        limit = limit or 40

        windowed = self._history[-limit:] if limit else self._history
        messages = (
            [{"role": "system", "content": self._agent.system_prompt}]
            + windowed
            + [{"role": "user", "content": message}]
        )

        result = await self._agent._run_messages(messages)

        # Run output guardrails
        self._agent._check_output_guardrails(result.content)

        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": result.content})

        if len(self._history) > limit:
            self._history = self._history[-limit:]

        return result

    def send_sync(self, message: str) -> Result:
        """Synchronous version of send()."""
        from ._sync import _run
        return _run(self.send(message))

    def start_sync(self) -> None:
        """Synchronous version of start()."""
        from ._sync import _run
        _run(self.start())

    async def start(self) -> None:
        """Start an interactive CLI chat session."""
        await self._agent._ensure_init()

        print("\nliteagent chat")
        print("=" * 40)
        print(f"Model: {self._agent._bundle.default_model_id}")
        print(f"Tools: {len(self._agent.tools)}")
        if self._agent._tool_filter:
            print(f"Scoped: {', '.join(self._agent._tool_filter)}")
        print("Commands: /tools /clear /help /quit")
        print("=" * 40 + "\n")

        while True:
            try:
                user_input = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            cmd = user_input.lower()
            if cmd == "/quit":
                print("\nGoodbye!")
                break
            elif cmd == "/tools":
                self._show_tools()
                continue
            elif cmd == "/clear":
                self.clear()
                print("[History cleared]\n")
                continue
            elif cmd == "/help":
                self._show_help()
                continue

            try:
                result = await self.send(user_input)
                print(f"\n{'─' * 60}")
                print(f"Assistant: {result.content}")
                print(f"{'─' * 60}\n")
            except Exception as e:
                print(f"\nError: {e}\n")

    def _show_tools(self) -> None:
        tools = self._agent.tools
        if not tools:
            print("\nNo tools loaded.\n")
            return

        print(f"\n{'=' * 40}")
        print(f"TOOLS ({len(tools)})")
        print(f"{'=' * 40}")
        for tool in tools:
            desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
            print(f"  {tool.name}")
            print(f"    {desc}")
        print(f"{'=' * 40}\n")

    def _show_help(self) -> None:
        print("""
Commands:
  /tools  - List available MCP tools
  /clear  - Clear conversation history
  /help   - Show this help
  /quit   - Exit
""")


def _cli_entry() -> None:
    """CLI entry point: `liteagent` command."""
    parser = argparse.ArgumentParser(
        prog="liteagent",
        description="Interactive chat with MCP tools via SafeChain",
    )
    parser.add_argument(
        "--system", "-s",
        default="You are a helpful assistant.",
        help="System prompt for the agent",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to liteagent.yaml (optional)",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Override model ID",
    )
    parser.add_argument(
        "--tools", "-t",
        nargs="*",
        default=None,
        help="Tool names to expose (default: all)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Max ReAct loop iterations",
    )
    args = parser.parse_args()

    chat = Chat(
        system_prompt=args.system,
        model=args.model,
        config=args.config,
        tools=args.tools,
        max_iterations=args.max_iterations,
        on_thinking=ConsoleCallback(use_rich=True),
    )

    asyncio.run(chat.start())
