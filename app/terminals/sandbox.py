"""Development terminal simulator — does not process real cards."""

from __future__ import annotations

from uuid import uuid4

from app.terminals.base import TerminalPaymentRequest, TerminalPaymentResult, TerminalProvider


class SandboxTerminalProvider(TerminalProvider):
    """
    TODO: Replace with official Sunmi / SoftPOS SDK adapter when documentation
    and certification requirements are provided by the client/processor.
    """

    provider_name = "sandbox_terminal"

    def __init__(self) -> None:
        self._connected = False

    async def initialize(self) -> None:
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def start_payment(self, request: TerminalPaymentRequest) -> TerminalPaymentResult:
        if not self._connected:
            return TerminalPaymentResult(
                success=False,
                status="FAILED",
                terminal_reference="",
                error_message="Terminal not connected (sandbox)",
            )
        if request.amount_minor <= 0:
            return TerminalPaymentResult(
                success=False,
                status="FAILED",
                terminal_reference="",
                error_message="Invalid amount",
            )
        ref = f"trm_sbx_{uuid4().hex[:12]}"
        # Decline path for explicit test metadata.
        if request.metadata.get("sandbox_scenario") == "declined":
            return TerminalPaymentResult(
                success=False,
                status="DECLINED",
                terminal_reference=ref,
                error_message="Sandbox terminal declined",
                raw={"simulator": True},
            )
        return TerminalPaymentResult(
            success=True,
            status="CAPTURED",
            terminal_reference=ref,
            raw={"simulator": True, "amount_minor": request.amount_minor},
        )

    async def cancel_payment(self, terminal_reference: str) -> TerminalPaymentResult:
        return TerminalPaymentResult(
            success=True,
            status="CANCELLED",
            terminal_reference=terminal_reference,
            raw={"simulator": True},
        )

    async def get_status(self, terminal_reference: str) -> TerminalPaymentResult:
        return TerminalPaymentResult(
            success=True,
            status="CAPTURED",
            terminal_reference=terminal_reference,
            raw={"simulator": True},
        )

    async def disconnect(self) -> None:
        self._connected = False
