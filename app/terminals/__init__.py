from app.terminals.base import TerminalProvider, TerminalPaymentRequest, TerminalPaymentResult
from app.terminals.sandbox import SandboxTerminalProvider

__all__ = [
    "TerminalProvider",
    "TerminalPaymentRequest",
    "TerminalPaymentResult",
    "SandboxTerminalProvider",
    "get_terminal_provider",
]


def get_terminal_provider(name: str | None = None) -> TerminalProvider:
    """Factory — only sandbox until an official SDK adapter is registered."""
    key = (name or "sandbox_terminal").lower()
    if key in {"sandbox", "sandbox_terminal"}:
        return SandboxTerminalProvider()
    raise ValueError(
        f"Terminal provider '{key}' is not configured. "
        "Add an official manufacturer SDK adapter when documentation is available."
    )
