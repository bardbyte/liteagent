"""Lazy cached bootstrap: CONFIG_PATH -> ee_config -> SafeChain tools.

This mirrors exactly what chat.py does in production:
    1. load_dotenv()          — load .env file
    2. Config.from_env()      — reads CONFIG_PATH env var -> YAML with mcp.servers
    3. MCPToolLoader.load_tools(config)  — connects to MCP servers, loads tools
    4. MCPToolAgent(model_id, tools)     — binds tools to LLM

The YAML that SafeChain expects (pointed to by CONFIG_PATH):

    mcp:
      servers:
        looker:
          url: https://toolbox-server.example.com
          transport: streamable-http

liteagent does NOT replace this config. It just wraps the init dance.
"""

import threading
from dataclasses import dataclass
from typing import Any

from ._config import LiteAgentConfig
from ._errors import BootstrapError

# Singleton cache — one bootstrap per process (tools are expensive to load)
_cache: "_BootstrapBundle | None" = None
_thread_lock = threading.Lock()  # guards cache reads/writes across threads + event loops


@dataclass
class _BootstrapBundle:
    """Cached result of a bootstrap operation."""
    tools: list[Any]
    tool_map: dict[str, Any]
    default_model_id: str
    config: LiteAgentConfig


def resolve_model_id(
    bundle: _BootstrapBundle,
    explicit: str | None = None,
) -> str:
    """Resolve model_id for a specific Agent. Does NOT mutate the cache.

    Priority: explicit arg > liteagent.yaml > ee_config > fallback.
    """
    return explicit or bundle.default_model_id


async def get(la_config: LiteAgentConfig) -> _BootstrapBundle:
    """Get or create the cached bootstrap bundle (tools + default model)."""
    global _cache

    if _cache is not None:
        return _cache

    with _thread_lock:
        # Double-check under lock
        if _cache is not None:
            return _cache

        _cache = await _init(la_config)
        return _cache


async def _init(la_config: LiteAgentConfig) -> _BootstrapBundle:
    """Perform the actual SafeChain initialization.

    This is the same 3-step dance that chat.py does:
        Config.from_env() -> MCPToolLoader.load_tools() -> resolve model_id
    """
    # Step 0: Load .env (same as chat.py — dotenv is required)
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())

    # Step 1: Load SafeChain config from CONFIG_PATH
    try:
        from ee_config.config import Config as EEConfig
    except ImportError as e:
        raise BootstrapError(
            "ee_config not installed. Install with: pip install ee_config",
            original=e,
        )

    # Step 2: Load MCP tools
    try:
        from safechain.tools.mcp import MCPToolLoader
    except ImportError as e:
        raise BootstrapError(
            "safechain not installed. Install with: pip install safechain",
            original=e,
        )

    try:
        ee_cfg = EEConfig.from_env()
    except Exception as e:
        raise BootstrapError(
            f"Config.from_env() failed. Is CONFIG_PATH set in your .env? Error: {e}",
            original=e,
        )

    try:
        tools = await MCPToolLoader.load_tools(ee_cfg)
    except Exception as e:
        raise BootstrapError(
            f"MCPToolLoader.load_tools() failed. Are MCP servers running? Error: {e}",
            original=e,
        )

    # Step 3: Resolve default model_id (same chain as chat.py lines 575-579)
    default_model = (
        la_config.model_id  # from liteagent.yaml (if set)
        or getattr(ee_cfg, "model_id", None)
        or getattr(ee_cfg, "model", None)
        or getattr(ee_cfg, "llm_model", None)
        or "gemini-pro"
    )

    tool_map = {tool.name: tool for tool in tools}

    return _BootstrapBundle(
        tools=tools,
        tool_map=tool_map,
        default_model_id=default_model,
        config=la_config,
    )


def clear_cache() -> None:
    """Clear the bootstrap cache. Useful for testing."""
    global _cache
    with _thread_lock:
        _cache = None
