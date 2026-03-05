"""Agent — ReAct loop with MCP tools.

This is the core of liteagent. It wraps MCPToolAgent (which is single-pass)
in a ReAct loop that continues until the LLM stops requesting tools.

Patterns implemented:
    - Tool scoping: restrict which tools an agent can see
    - Guardrails: pre/post validation hooks
    - Retry: automatic retry on tool errors
    - Streaming: async generator of thinking events
    - Structured output: parse final answer as typed data
"""

import json
import re
from typing import Any, AsyncIterator, Callable, Type

from ._bootstrap import get as _get_bundle, resolve_model_id
from ._config import LiteAgentConfig
from ._errors import BootstrapError, GuardrailError
from ._result import Result, ToolCall
from ._thinking import (
    ThinkingCallback, ThinkingEvent, ThinkingType, _wrap_callback,
)

# Type alias for guardrail functions
# Returns None to allow, or error message string to block
Guardrail = Callable[[str], str | None]


class Agent:
    """Agentic workflow with a ReAct loop over MCP tools.

    Args:
        system_prompt: System prompt for the LLM.
        model: Override model_id from config.
        config: Path to liteagent.yaml (optional).
        tools: List of tool names to expose. None = all tools.
        max_iterations: Max ReAct loop iterations.
        max_retries: Retry count when a tool errors.
        on_thinking: Callback for real-time thinking events.
        input_guardrails: Functions that validate user input before LLM call.
        output_guardrails: Functions that validate LLM output before returning.

    Example::

        from liteagent import Agent

        agent = Agent(
            system_prompt="You are a Looker expert",
            tools=["conversational-analytics", "get-models", "get-explores"],
        )
        result = await agent.run("What models are available?")
        print(result.content)
        print(result.tool_calls)
    """

    def __init__(
        self,
        system_prompt: str = "You are a helpful assistant.",
        *,
        model: str | None = None,
        config: str | None = None,
        tools: list[str] | None = None,
        max_iterations: int | None = None,
        max_retries: int = 0,
        on_thinking: ThinkingCallback | Callable[[ThinkingEvent], None] | None = None,
        input_guardrails: list[Guardrail] | None = None,
        output_guardrails: list[Guardrail] | None = None,
    ):
        self.system_prompt = system_prompt
        self._model = model
        self._config_path = config
        self._tool_filter = tools
        self._max_iterations = max_iterations
        self._max_retries = max_retries
        self._on_thinking = _wrap_callback(on_thinking)
        self._input_guardrails = input_guardrails or []
        self._output_guardrails = output_guardrails or []

        # Lazy-initialized
        self._bundle = None
        self._scoped_tools: list[Any] | None = None
        self._mcp_agent: MCPToolAgent | None = None

    async def _ensure_init(self) -> None:
        """Lazy bootstrap on first use."""
        if self._bundle is not None:
            return

        cfg = LiteAgentConfig.resolve(self._config_path)
        self._bundle = await _get_bundle(cfg)

        # Tool scoping: filter to only requested tools
        if self._tool_filter is not None:
            available = self._bundle.tool_map
            missing = [t for t in self._tool_filter if t not in available]
            if missing:
                all_names = sorted(available.keys())
                raise BootstrapError(
                    f"Requested tools not found: {missing}. "
                    f"Available: {all_names}"
                )
            self._scoped_tools = [available[t] for t in self._tool_filter]
        else:
            self._scoped_tools = self._bundle.tools

        # Each Agent resolves its own model_id without mutating the cache
        # Lazy import — safechain is only needed at runtime, not at import time
        from safechain.tools.mcp import MCPToolAgent

        model_id = resolve_model_id(self._bundle, self._model)
        self._mcp_agent = MCPToolAgent(model_id, self._scoped_tools)

        if self._max_iterations is None:
            self._max_iterations = self._bundle.config.max_iterations

    @property
    def tools(self) -> list:
        """List of loaded MCP tools (empty until first run)."""
        if self._scoped_tools is not None:
            return self._scoped_tools
        return self._bundle.tools if self._bundle else []

    @property
    def tool_names(self) -> list[str]:
        """Names of available tools."""
        return [t.name for t in self.tools]

    def _emit(self, event: ThinkingEvent) -> None:
        if self._on_thinking:
            self._on_thinking.on_thinking(event)

    def _check_input_guardrails(self, prompt: str) -> None:
        """Run input guardrails. Raises GuardrailError if blocked."""
        for guardrail in self._input_guardrails:
            error = guardrail(prompt)
            if error:
                name = getattr(guardrail, "__name__", "input_guardrail")
                raise GuardrailError(error, guardrail_name=name)

    def _check_output_guardrails(self, content: str) -> None:
        """Run output guardrails. Raises GuardrailError if blocked."""
        for guardrail in self._output_guardrails:
            error = guardrail(content)
            if error:
                name = getattr(guardrail, "__name__", "output_guardrail")
                raise GuardrailError(error, guardrail_name=name)

    async def run(
        self,
        prompt: str,
        *,
        output_type: Type | None = None,
    ) -> Result:
        """Run a single user prompt through the ReAct loop.

        Args:
            prompt: The user's question or instruction.
            output_type: Optional Pydantic model or type to parse the response into.
                         Sets result.parsed if parsing succeeds.

        Returns:
            Result with content, tool_calls, iterations, and thinking events.
        """
        self._check_input_guardrails(prompt)
        await self._ensure_init()

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        # If structured output is requested, amend the prompt
        if output_type is not None:
            schema_hint = _schema_instruction(output_type)
            messages[-1]["content"] = f"{prompt}\n\n{schema_hint}"

        result = await self._run_messages(messages)

        # Output guardrails
        self._check_output_guardrails(result.content)

        # Structured output parsing
        if output_type is not None:
            result.parsed = _parse_output(result.content, output_type)

        return result

    def run_sync(self, prompt: str, **kwargs) -> Result:
        """Synchronous version of run()."""
        from ._sync import _run
        return _run(self.run(prompt, **kwargs))

    async def stream(self, prompt: str) -> AsyncIterator[ThinkingEvent]:
        """Stream thinking events as they happen.

        Example::

            async for event in agent.stream("What models are available?"):
                if event.type == ThinkingType.FINAL_ANSWER:
                    print(event.content)
        """
        self._check_input_guardrails(prompt)
        await self._ensure_init()

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        async for event in self._stream_messages(messages):
            yield event

    async def _run_messages(self, messages: list[dict]) -> Result:
        """Core ReAct loop. Used by Agent.run() and Chat.send().

        MCPToolAgent is single-pass: call LLM → execute tools → return.
        This loop calls it repeatedly until the LLM stops requesting tools.
        """
        await self._ensure_init()

        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        thinking_events: list[ThinkingEvent] = []
        tool_calls: list[ToolCall] = []
        iteration = 0
        content = ""
        retries_left = self._max_retries

        while iteration < self._max_iterations:
            iteration += 1

            lc_messages = _to_langchain(messages)

            try:
                raw = await self._mcp_agent.ainvoke(lc_messages)
            except Exception as e:
                if retries_left > 0:
                    retries_left -= 1
                    event = ThinkingEvent(
                        type=ThinkingType.ERROR,
                        content=f"Error (retrying, {retries_left} left): {e}",
                    )
                    self._emit(event)
                    thinking_events.append(event)
                    continue

                event = ThinkingEvent(type=ThinkingType.ERROR, content=f"Agent error: {e}")
                self._emit(event)
                thinking_events.append(event)
                return Result(
                    content=f"I encountered an error: {e}",
                    tool_calls=tool_calls,
                    iterations=iteration,
                    thinking=thinking_events,
                )

            # Parse result
            if isinstance(raw, dict):
                content = raw.get("content", "")
                tool_results = raw.get("tool_results", [])
            else:
                content = getattr(raw, "content", str(raw))
                tool_results = []

            # Process tool calls
            if tool_results:
                for tr in tool_results:
                    tool_name = tr.get("tool", "unknown")

                    # Emit tool call event
                    self._emit(ThinkingEvent(
                        type=ThinkingType.TOOL_CALL,
                        content=f"Executing: {tool_name}",
                        metadata={"tool_name": tool_name},
                    ))

                    # Record and emit result
                    # Note: MCPToolAgent already executed tools before returning,
                    # so we can't measure individual tool duration here.
                    if "error" in tr:
                        tc = ToolCall(name=tool_name, error=tr["error"])
                        event = ThinkingEvent(
                            type=ThinkingType.ERROR,
                            content=f"Error: {tr['error']}",
                            metadata={"tool_name": tool_name},
                        )
                    else:
                        result_str = str(tr.get("result", ""))
                        tc = ToolCall(name=tool_name, result=result_str)
                        display = (
                            result_str[:500] + "..."
                            if len(result_str) > 500
                            else result_str
                        )
                        event = ThinkingEvent(
                            type=ThinkingType.TOOL_RESULT,
                            content=display,
                            metadata={"tool_name": tool_name},
                        )

                    tool_calls.append(tc)
                    self._emit(event)
                    thinking_events.append(event)

                # Add assistant reasoning
                if content:
                    messages.append({"role": "assistant", "content": content})
                    reasoning = ThinkingEvent(
                        type=ThinkingType.REASONING, content=content
                    )
                    self._emit(reasoning)
                    thinking_events.append(reasoning)

                # Add tool results for next iteration
                for tr in tool_results:
                    tool_name = tr.get("tool", "unknown")
                    tool_content = (
                        f"Error: {tr['error']}"
                        if "error" in tr
                        else str(tr.get("result", ""))
                    )
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": tool_content,
                        "tool_call_id": f"call_{iteration}_{tool_name}",
                    })

                # Reset retries on successful iteration
                retries_left = self._max_retries
                continue

            # No tool calls — final answer
            if content:
                event = ThinkingEvent(
                    type=ThinkingType.FINAL_ANSWER, content=content
                )
                self._emit(event)
                thinking_events.append(event)

            return Result(
                content=content,
                tool_calls=tool_calls,
                iterations=iteration,
                thinking=thinking_events,
            )

        # Max iterations
        return Result(
            content=(
                f"Reached maximum iterations ({self._max_iterations}). "
                f"Last response: {content}"
            ),
            tool_calls=tool_calls,
            iterations=iteration,
            thinking=thinking_events,
        )

    async def _stream_messages(
        self, messages: list[dict]
    ) -> AsyncIterator[ThinkingEvent]:
        """Streaming version of _run_messages — yields events as they happen."""
        await self._ensure_init()

        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        iteration = 0
        content = ""

        while iteration < self._max_iterations:
            iteration += 1
            lc_messages = _to_langchain(messages)

            try:
                raw = await self._mcp_agent.ainvoke(lc_messages)
            except Exception as e:
                yield ThinkingEvent(type=ThinkingType.ERROR, content=f"Error: {e}")
                return

            if isinstance(raw, dict):
                content = raw.get("content", "")
                tool_results = raw.get("tool_results", [])
            else:
                content = getattr(raw, "content", str(raw))
                tool_results = []

            if tool_results:
                for tr in tool_results:
                    tool_name = tr.get("tool", "unknown")
                    yield ThinkingEvent(
                        type=ThinkingType.TOOL_CALL,
                        content=f"Executing: {tool_name}",
                        metadata={"tool_name": tool_name},
                    )

                    if "error" in tr:
                        yield ThinkingEvent(
                            type=ThinkingType.ERROR,
                            content=f"Error: {tr['error']}",
                            metadata={"tool_name": tool_name},
                        )
                    else:
                        result_str = str(tr.get("result", ""))
                        display = result_str[:500] + "..." if len(result_str) > 500 else result_str
                        yield ThinkingEvent(
                            type=ThinkingType.TOOL_RESULT,
                            content=display,
                            metadata={"tool_name": tool_name},
                        )

                if content:
                    messages.append({"role": "assistant", "content": content})
                    yield ThinkingEvent(type=ThinkingType.REASONING, content=content)

                for tr in tool_results:
                    tool_name = tr.get("tool", "unknown")
                    tool_content = (
                        f"Error: {tr['error']}"
                        if "error" in tr
                        else str(tr.get("result", ""))
                    )
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": tool_content,
                        "tool_call_id": f"call_{iteration}_{tool_name}",
                    })
                continue

            if content:
                yield ThinkingEvent(type=ThinkingType.FINAL_ANSWER, content=content)
            return

        yield ThinkingEvent(
            type=ThinkingType.ERROR,
            content=f"Reached max iterations ({self._max_iterations})",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_langchain(messages: list[dict]) -> list:
    """Convert dict messages to LangChain message objects."""
    from langchain_core.messages import (
        AIMessage, HumanMessage, SystemMessage, ToolMessage,
    )

    lc = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            lc.append(SystemMessage(content=content))
        elif role == "user":
            lc.append(HumanMessage(content=content))
        elif role == "assistant":
            lc.append(AIMessage(content=content))
        elif role == "tool":
            lc.append(ToolMessage(
                content=content,
                tool_call_id=msg.get("tool_call_id", ""),
                name=msg.get("name", ""),
            ))
    return lc


def _schema_instruction(output_type: Type) -> str:
    """Generate a JSON schema instruction for structured output."""
    if hasattr(output_type, "model_json_schema"):
        # Pydantic v2
        schema = output_type.model_json_schema()
        return (
            "IMPORTANT: Respond with ONLY valid JSON matching this schema "
            f"(no markdown, no explanation):\n{json.dumps(schema, indent=2)}"
        )
    # Fallback for plain types
    return "IMPORTANT: Respond with ONLY valid JSON (no markdown, no explanation)."


def _parse_output(content: str, output_type: Type) -> Any:
    """Parse LLM output into the requested type."""
    # Extract JSON from possible markdown code blocks
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    json_str = json_match.group(1).strip() if json_match else content.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    if hasattr(output_type, "model_validate"):
        # Pydantic v2
        try:
            return output_type.model_validate(data)
        except Exception:
            return None

    # Plain dict/list
    if output_type in (dict, list):
        return data

    return data
