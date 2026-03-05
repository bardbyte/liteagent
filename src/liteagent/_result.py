"""Result dataclasses returned by Agent and call()."""

from dataclasses import dataclass, field
from typing import Any

from ._thinking import ThinkingEvent

@dataclass
class ToolCall:
    """Record of a single tool invocation."""
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass
class Result:
    """Outcome of an agent run or one-shot call.

    Attributes:
        content: The final text answer.
        tool_calls: Ordered list of tools that were invoked.
        iterations: Number of ReAct loop iterations.
        thinking: Sequence of thinking events for debugging/viz.
        parsed: Structured output (set when output_type is used).
    """
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    iterations: int = 0
    thinking: list[ThinkingEvent] = field(default_factory=list)
    parsed: Any = None

    def __str__(self) -> str:
        return self.content

    def __bool__(self) -> bool:
        return bool(self.content)

    @property
    def tools_used(self) -> list[str]:
        """Unique tool names that were called, in order."""
        seen = set()
        names = []
        for tc in self.tool_calls:
            if tc.name not in seen:
                seen.add(tc.name)
                names.append(tc.name)
        return names

    @property
    def has_errors(self) -> bool:
        return any(not tc.ok for tc in self.tool_calls)

    @property
    def failed_tools(self) -> list[ToolCall]:
        return [tc for tc in self.tool_calls if not tc.ok]
