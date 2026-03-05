"""Config for liteagent-specific settings.

SafeChain config is NOT managed here — it comes from CONFIG_PATH env var
as it always has. This module only handles liteagent's own settings
(model overrides, iteration limits, etc.).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ._errors import ConfigNotFoundError

# Search order for liteagent settings file (NOT the SafeChain config)
_SEARCH_PATHS = [
    lambda: os.environ.get("LITEAGENT_CONFIG", ""),
    lambda: str(Path.cwd() / "liteagent.yaml"),
    lambda: str(Path.home() / ".config" / "liteagent" / "config.yaml"),
]


@dataclass
class LiteAgentConfig:
    """Liteagent-specific settings. Optional — everything has defaults.

    This does NOT replace SafeChain's ee_config. SafeChain still reads
    its own config from CONFIG_PATH env var. This file only holds
    liteagent knobs like model_id overrides and iteration limits.
    """
    path: str = ""
    model_id: str = ""
    max_iterations: int = 15
    history_limit: int = 40
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def resolve(cls, config_path: str | None = None) -> "LiteAgentConfig":
        """Find and parse a liteagent settings file.

        Returns defaults if no file is found — this is NOT an error.
        SafeChain config (CONFIG_PATH) is separate and required.
        """
        if config_path:
            p = Path(config_path).expanduser().resolve()
            if p.is_file():
                return cls._parse(str(p))
            # Explicit path given but not found — that IS an error
            raise ConfigNotFoundError([str(p)])

        # Search default locations — but missing is fine
        for path_fn in _SEARCH_PATHS:
            candidate = path_fn()
            if not candidate:
                continue
            p = Path(candidate).expanduser().resolve()
            if p.is_file():
                return cls._parse(str(p))

        # No file found — return defaults (this is normal)
        return cls()

    @classmethod
    def _parse(cls, path: str) -> "LiteAgentConfig":
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        la = raw.get("liteagent", raw)

        return cls(
            path=path,
            model_id=la.get("model_id", ""),
            max_iterations=la.get("max_iterations", 15),
            history_limit=la.get("history_limit", 40),
            raw=raw,
        )
