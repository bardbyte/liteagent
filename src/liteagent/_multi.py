"""Multi-agent patterns: Router and Pipeline.

Router: routes user messages to the right specialist agent.
Pipeline: chains agents sequentially — output of one feeds the next.
"""

from typing import Callable

from ._agent import Agent
from ._result import Result


class Router:
    """Routes messages to specialist agents based on a routing function.

    The router picks which agent handles a given message. Useful when you have
    agents specialized for different tasks (data queries, formatting, schema).

    Example::

        from liteagent import Agent, Router

        analyst = Agent(
            system_prompt="You analyze data",
            tools=["query", "get-dimensions", "get-measures"],
        )
        schema = Agent(
            system_prompt="You explore schemas",
            tools=["get-models", "get-explores"],
        )
        general = Agent(system_prompt="You answer general questions")

        def route(message: str) -> str:
            msg = message.lower()
            if any(w in msg for w in ["model", "explore", "schema", "field"]):
                return "schema"
            if any(w in msg for w in ["revenue", "sales", "count", "total", "query"]):
                return "analyst"
            return "general"

        router = Router(
            agents={"analyst": analyst, "schema": schema, "general": general},
            route=route,
            default="general",
        )

        result = await router.run("What models are available?")
        print(result.content)
    """

    def __init__(
        self,
        agents: dict[str, Agent],
        route: Callable[[str], str],
        default: str | None = None,
    ):
        self.agents = agents
        self._route = route
        self._default = default or next(iter(agents))

    async def run(self, prompt: str, **kwargs) -> Result:
        """Route the prompt to the appropriate agent and run it."""
        agent_key = self._route(prompt)
        if agent_key not in self.agents:
            agent_key = self._default
        return await self.agents[agent_key].run(prompt, **kwargs)

    def run_sync(self, prompt: str, **kwargs) -> Result:
        from ._sync import _run
        return _run(self.run(prompt, **kwargs))


class Pipeline:
    """Chains agents sequentially — each agent's output feeds the next.

    Useful for multi-step workflows:
    1. Agent A extracts data
    2. Agent B analyzes it
    3. Agent C formats a report

    Each agent receives the previous agent's output as its prompt, optionally
    transformed by a custom function.

    Example::

        from liteagent import Agent, Pipeline

        extractor = Agent(
            system_prompt="Extract raw data from Looker",
            tools=["query", "conversational-analytics"],
        )
        analyst = Agent(system_prompt="Analyze data and find insights")
        writer = Agent(system_prompt="Write a concise executive summary")

        pipe = Pipeline(steps=[extractor, analyst, writer])
        result = await pipe.run("Q4 revenue by region vs last year")

        # result.content = executive summary
        # pipe.intermediate_results = [extractor_result, analyst_result, writer_result]
    """

    def __init__(
        self,
        steps: list[Agent],
        transforms: list[Callable[[str], str] | None] | None = None,
    ):
        self.steps = steps
        self._transforms = transforms or [None] * len(steps)
        self.intermediate_results: list[Result] = []

    async def run(self, prompt: str, **kwargs) -> Result:
        """Run the pipeline, passing output through each step."""
        self.intermediate_results = []
        current_input = prompt

        for i, agent in enumerate(self.steps):
            # Apply transform if provided
            transform = self._transforms[i] if i < len(self._transforms) else None
            if transform is not None:
                current_input = transform(current_input)

            result = await agent.run(current_input, **kwargs)
            self.intermediate_results.append(result)

            # Next agent gets this agent's output
            current_input = result.content

        # Final result is the last agent's output, but aggregate tool_calls
        final = self.intermediate_results[-1] if self.intermediate_results else Result()
        all_tool_calls = []
        total_iterations = 0
        all_thinking = []
        for r in self.intermediate_results:
            all_tool_calls.extend(r.tool_calls)
            total_iterations += r.iterations
            all_thinking.extend(r.thinking)

        return Result(
            content=final.content,
            tool_calls=all_tool_calls,
            iterations=total_iterations,
            thinking=all_thinking,
            parsed=final.parsed,
        )

    def run_sync(self, prompt: str, **kwargs) -> Result:
        from ._sync import _run
        return _run(self.run(prompt, **kwargs))
