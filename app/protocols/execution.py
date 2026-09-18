"""Protocol execution — production never dummy-approves undocumented profiles."""

from __future__ import annotations

from dataclasses import dataclass

from app.exceptions.base import AppException
from app.protocols import ProtocolDefinition, get_protocol


@dataclass(frozen=True, slots=True)
class ProtocolExecutionDecision:
    allowed: bool
    status: str
    reason: str


def decide_protocol_execution(
    protocol_code: str | None,
    *,
    environment: str,
) -> ProtocolExecutionDecision:
    env = (environment or "sandbox").lower()
    definition: ProtocolDefinition | None = None
    if protocol_code:
        try:
            definition = get_protocol(protocol_code)
        except KeyError:
            definition = None
    if env in {"production", "prod"}:
        if definition is None or not definition.documented:
            return ProtocolExecutionDecision(
                allowed=False,
                status="PROVIDER_CONFIGURATION_REQUIRED",
                reason=(
                    "Protocol is a client catalog label only. Official processor "
                    "documentation is required before production authorization."
                ),
            )
    return ProtocolExecutionDecision(
        allowed=True,
        status="SANDBOX_SIMULATION" if env != "production" else "DOCUMENTED",
        reason="Sandbox mock processor may simulate outcomes. Not card-network authorization.",
    )


def require_protocol_execution(protocol_code: str | None, *, environment: str) -> None:
    decision = decide_protocol_execution(protocol_code, environment=environment)
    if not decision.allowed:
        raise AppException(decision.reason, status_code=503)
