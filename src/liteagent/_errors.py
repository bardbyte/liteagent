"""Custom exceptions for liteagent."""


class ConfigNotFoundError(FileNotFoundError):
    """Raised when no liteagent config file can be found."""

    def __init__(self, searched: list[str] | None = None):
        paths = ", ".join(searched) if searched else "default locations"
        super().__init__(f"No liteagent config found. Searched: {paths}")
        self.searched = searched or []


class BootstrapError(RuntimeError):
    """Raised when SafeChain initialization fails."""

    def __init__(self, reason: str, original: Exception | None = None):
        super().__init__(f"Bootstrap failed: {reason}")
        self.original = original


class GuardrailError(ValueError):
    """Raised when a guardrail blocks a request or response."""

    def __init__(self, message: str, guardrail_name: str = ""):
        super().__init__(message)
        self.guardrail_name = guardrail_name
