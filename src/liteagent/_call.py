"""One-shot LLM call — no tool loop, just prompt -> response."""

from ._bootstrap import get as _get_bundle, resolve_model_id
from ._config import LiteAgentConfig
from ._result import Result


async def call(
    prompt: str,
    *,
    system: str = "",
    model: str | None = None,
    config: str | None = None,
) -> Result:
    """Make a single LLM call through SafeChain. No ReAct loop, no tool execution.

    Args:
        prompt: The user prompt.
        system: Optional system prompt.
        model: Override model_id.
        config: Path to liteagent.yaml (optional).

    Returns:
        Result with .content set to the LLM response.

    Example::

        from liteagent import call
        result = await call("Summarize this data", system="You are a data analyst")
        print(result)
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from safechain.tools.mcp import MCPToolAgent

    cfg = LiteAgentConfig.resolve(config)
    bundle = await _get_bundle(cfg)

    model_id = resolve_model_id(bundle, model)
    agent = MCPToolAgent(model_id, bundle.tools)

    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))

    raw = await agent.ainvoke(messages)

    content = ""
    if isinstance(raw, dict):
        content = raw.get("content", "")
    else:
        content = getattr(raw, "content", str(raw))

    return Result(content=content, iterations=1)
