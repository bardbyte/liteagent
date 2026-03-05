"""Thinking events for real-time agent visualization."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ThinkingType(str, Enum):
    """Types of thinking events."""
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"


@dataclass
class ThinkingEvent:
    """A single thinking event from the agent."""
    type: ThinkingType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ThinkingCallback(ABC):
    """Abstract callback for receiving thinking events."""

    @abstractmethod
    def on_thinking(self, event: ThinkingEvent) -> None:
        pass


class ConsoleCallback(ThinkingCallback):
    """Prints thinking events to console with optional rich formatting."""

    def __init__(self, use_rich: bool = True):
        self.use_rich = use_rich
        self._console = None

        if use_rich:
            try:
                from rich.console import Console
                self._console = Console()
            except ImportError:
                self.use_rich = False

    def on_thinking(self, event: ThinkingEvent) -> None:
        if self.use_rich and self._console:
            self._print_rich(event)
        else:
            self._print_plain(event)

    def _print_rich(self, event: ThinkingEvent) -> None:
        from rich.panel import Panel
        from rich.markdown import Markdown

        styles = {
            ThinkingType.REASONING: ("bold blue", "Thinking"),
            ThinkingType.TOOL_CALL: ("bold yellow", "Tool Call"),
            ThinkingType.TOOL_RESULT: ("bold green", "Tool Result"),
            ThinkingType.FINAL_ANSWER: ("bold cyan", "Answer"),
            ThinkingType.ERROR: ("bold red", "Error"),
        }

        style, title = styles.get(event.type, ("white", "Event"))

        if event.type == ThinkingType.TOOL_CALL:
            tool_name = event.metadata.get("tool_name", "unknown")
            title = f"Tool Call: {tool_name}"

        content = event.content
        if event.type in (ThinkingType.REASONING, ThinkingType.FINAL_ANSWER):
            try:
                content = Markdown(event.content)
            except Exception:
                pass

        self._console.print(Panel(content, title=title, style=style, expand=False))

    def _print_plain(self, event: ThinkingEvent) -> None:
        prefixes = {
            ThinkingType.REASONING: "[THINKING]",
            ThinkingType.TOOL_CALL: "[TOOL CALL]",
            ThinkingType.TOOL_RESULT: "[TOOL RESULT]",
            ThinkingType.FINAL_ANSWER: "[ANSWER]",
            ThinkingType.ERROR: "[ERROR]",
        }

        prefix = prefixes.get(event.type, "[EVENT]")
        if event.type == ThinkingType.TOOL_CALL:
            tool_name = event.metadata.get("tool_name", "unknown")
            prefix = f"[TOOL CALL: {tool_name}]"

        print(f"\n{prefix}")
        print("-" * 50)
        print(event.content)
        print("-" * 50)


def _wrap_callback(
    on_thinking: ThinkingCallback | Callable[[ThinkingEvent], None] | None,
) -> ThinkingCallback | None:
    """Wrap a plain function as a ThinkingCallback, or pass through."""
    if on_thinking is None:
        return None
    if isinstance(on_thinking, ThinkingCallback):
        return on_thinking

    # Wrap a plain callable
    class _FnCallback(ThinkingCallback):
        def __init__(self, fn: Callable[[ThinkingEvent], None]):
            self._fn = fn

        def on_thinking(self, event: ThinkingEvent) -> None:
            self._fn(event)

    return _FnCallback(on_thinking)
