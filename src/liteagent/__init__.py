"""liteagent — SafeChain made simple.

Three APIs for three use cases::

    # 1. One-shot LLM call
    from liteagent import call
    result = await call("Summarize this data", system="You are a data analyst")

    # 2. Agentic workflow with ReAct loop + tool scoping
    from liteagent import Agent
    agent = Agent(
        system_prompt="You are a Looker expert",
        tools=["conversational-analytics", "get-models"],
    )
    result = await agent.run("What models are available?")

    # 3. Interactive chat
    from liteagent import Chat
    chat = Chat(system_prompt="You are a data analyst")
    await chat.start()

Multi-agent patterns::

    from liteagent import Agent, Router, Pipeline

    # Router: pick the right agent for the job
    router = Router(
        agents={"data": data_agent, "schema": schema_agent},
        route=lambda msg: "schema" if "model" in msg else "data",
    )

    # Pipeline: chain agents sequentially
    pipe = Pipeline(steps=[extractor, analyst, writer])
    result = await pipe.run("Q4 revenue analysis")
"""

from ._adk import LiteAgent
from ._agent import Agent
from ._bootstrap import clear_cache
from ._call import call
from ._chat import Chat
from ._config import LiteAgentConfig
from ._errors import BootstrapError, ConfigNotFoundError, GuardrailError
from ._multi import Pipeline, Router
from ._result import Result, ToolCall
from ._sync import call_sync
from ._thinking import (
    ConsoleCallback,
    ThinkingCallback,
    ThinkingEvent,
    ThinkingType,
)

__all__ = [
    # Core APIs
    "call",
    "call_sync",
    "Agent",
    "Chat",
    # Multi-agent
    "Router",
    "Pipeline",
    # ADK integration
    "LiteAgent",
    # Result types
    "Result",
    "ToolCall",
    # Config
    "LiteAgentConfig",
    # Thinking / callbacks
    "ThinkingEvent",
    "ThinkingType",
    "ThinkingCallback",
    "ConsoleCallback",
    # Errors
    "ConfigNotFoundError",
    "BootstrapError",
    "GuardrailError",
    # Utilities
    "clear_cache",
]
