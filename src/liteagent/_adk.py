"""Google ADK (Agent Development Kit) adapter.

Wraps liteagent's ReAct loop as an ADK BaseAgent so it can participate in
ADK multi-agent orchestration (SequentialAgent, ParallelAgent, LoopAgent,
LLM-driven transfer, AgentTool).

Usage::

    from liteagent import LiteAgent
    from google.adk.agents import SequentialAgent, LlmAgent
    from google.adk.runners import InMemoryRunner

    # Your ReAct agent as an ADK agent
    looker = LiteAgent(
        name="LookerAnalyst",
        description="Queries Looker semantic layer via MCP tools",
        system_prompt="You are a Looker analytics expert...",
        tool_names=["conversational-analytics", "get-models", "query"],
    )

    # Use it inside ADK orchestration
    pipeline = SequentialAgent(
        name="AnalyticsPipeline",
        sub_agents=[
            LlmAgent(name="Planner", model="gemini-2.5-flash",
                     instruction="Plan the query.", output_key="plan"),
            looker,
            LlmAgent(name="Summarizer", model="gemini-2.5-flash",
                     instruction="Summarize {looker_result}."),
        ],
    )

    runner = InMemoryRunner(agent=pipeline)

Requires: pip install google-adk
"""

from __future__ import annotations

from typing import Any, AsyncGenerator

try:
    from google.adk.agents import BaseAgent
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.events import Event
    from google.genai import types as genai_types

    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False


def _require_adk():
    if not ADK_AVAILABLE:
        raise ImportError(
            "google-adk is required for ADK integration. "
            "Install with: pip install google-adk"
        )


if ADK_AVAILABLE:

    class LiteAgent(BaseAgent):
        """ADK-compatible agent powered by liteagent's ReAct loop.

        This bridges two worlds:
        - liteagent handles LLM calls + MCP tool execution via SafeChain
        - ADK handles multi-agent orchestration, sessions, and deployment

        The ReAct loop (MCPToolAgent.ainvoke → check tool_results → loop)
        runs inside _run_async_impl, yielding ADK Events at each step.

        Attributes:
            system_prompt: System prompt for the LLM.
            model_id: Model ID override (default from SafeChain config).
            tool_names: MCP tool names to scope. None = all tools.
            max_iterations: Max ReAct loop iterations.
            output_key: If set, saves final answer to session.state[key].
            config: Path to liteagent.yaml (optional).
        """

        # Pydantic fields (ADK BaseAgent uses Pydantic)
        system_prompt: str = "You are a helpful assistant."
        model_id: str | None = None  # avoid 'model' — conflicts with Pydantic namespace
        tool_names: list[str] | None = None
        max_iterations: int = 15
        output_key: str = ""
        config: str | None = None

        model_config = {"arbitrary_types_allowed": True}

        def model_post_init(self, __context: Any) -> None:
            """Initialize private state after Pydantic construction."""
            self.__dict__["_lite_agent"] = None

        async def _ensure_agent(self) -> None:
            """Lazily create the underlying liteagent Agent."""
            if self.__dict__.get("_lite_agent") is not None:
                return

            from ._agent import Agent

            agent = Agent(
                system_prompt=self.system_prompt,
                model=self.model_id,
                config=self.config,
                tools=self.tool_names,
                max_iterations=self.max_iterations,
            )
            await agent._ensure_init()
            self.__dict__["_lite_agent"] = agent

        async def _run_async_impl(
            self, ctx: InvocationContext
        ) -> AsyncGenerator[Event, None]:
            """Run the ReAct loop, yielding ADK Events.

            Delegates to Agent._run_messages() so the ReAct loop exists in
            one place. Any bug fixes to the loop automatically apply here.
            """
            await self._ensure_agent()

            # Extract user message from ADK invocation context
            user_message = self._extract_user_message(ctx)
            if not user_message:
                yield Event(
                    author=self.name,
                    content=genai_types.Content(
                        role="model",
                        parts=[genai_types.Part(text="No input provided.")],
                    ),
                )
                return

            # Build message history from ADK session state
            messages = self._build_messages(ctx, user_message)

            # Delegate to the single ReAct loop in Agent._run_messages()
            agent = self.__dict__["_lite_agent"]
            try:
                result = await agent._run_messages(messages)
            except Exception as e:
                yield Event(
                    author=self.name,
                    content=genai_types.Content(
                        role="model",
                        parts=[genai_types.Part(text=f"Error: {e}")],
                    ),
                )
                return

            # Yield tool execution events for ADK observability
            from ._thinking import ThinkingType

            for event in result.thinking:
                if event.type in (ThinkingType.TOOL_CALL, ThinkingType.TOOL_RESULT, ThinkingType.ERROR):
                    yield Event(
                        author=self.name,
                        content=genai_types.Content(
                            role="model",
                            parts=[genai_types.Part(text=event.content)],
                        ),
                    )

            # Final answer
            yield Event(
                author=self.name,
                content=genai_types.Content(
                    role="model",
                    parts=[genai_types.Part(text=result.content)],
                ),
            )

            # Save to session state if output_key is set
            if self.output_key and result.content:
                ctx.session.state[self.output_key] = result.content

        def _extract_user_message(self, ctx: InvocationContext) -> str:
            """Extract the user's text message from the ADK context."""
            if hasattr(ctx, "user_content") and ctx.user_content:
                if hasattr(ctx.user_content, "parts") and ctx.user_content.parts:
                    for part in ctx.user_content.parts:
                        if hasattr(part, "text") and part.text:
                            return part.text
            return ""

        def _build_messages(
            self, ctx: InvocationContext, user_message: str
        ) -> list[dict]:
            """Build the message list for the ReAct loop from ADK context."""
            messages = [{"role": "system", "content": self.system_prompt}]

            # Pull prior context from session state if available
            prior = ctx.session.state.get("_liteagent_history", [])
            if isinstance(prior, list):
                messages.extend(prior)

            messages.append({"role": "user", "content": user_message})
            return messages

else:
    # ADK not installed — provide a stub that gives a clear error
    class LiteAgent:  # type: ignore[no-redef]
        """Stub — install google-adk to use ADK integration."""

        def __init__(self, **kwargs):
            _require_adk()
