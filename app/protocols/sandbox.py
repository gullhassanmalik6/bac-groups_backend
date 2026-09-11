"""Sandbox protocol adapter — mocked responses only. Never talks to card networks."""

from __future__ import annotations

from uuid import uuid4

from app.protocols import ProtocolDefinition, ProtocolRequest, ProtocolResponse


class SandboxProtocolAdapter:
    """Deterministic mock adapter implementing PaymentProtocolAdapter methods.

    Does not invent host message bytes. Maps catalog sandbox_outcome → status only.
    """

    def validate_request(self, definition: ProtocolDefinition, request: ProtocolRequest) -> None:
        if request.amount_minor <= 0:
            raise ValueError("amount_minor must be positive")
        if not request.payment_token.startswith("pm_test_"):
            raise ValueError("Sandbox protocol requires pm_test_* payment token")

    def build_request(self, definition: ProtocolDefinition, request: ProtocolRequest) -> dict:
        self.validate_request(definition, request)
        return {
            "protocol_selection_id": definition.selection_id,
            "protocol_code": definition.code,
            "transaction_id": request.transaction_id,
            "amount_minor": request.amount_minor,
            "currency": request.currency,
            "payment_token": request.payment_token,
            "sandbox_outcome": definition.sandbox_outcome,
            "connectivity": definition.connectivity,
            "digit_group": definition.digit_group,
            # Explicit: no PAN/CVV/track data ever included.
        }

    def validate_response(self, response: ProtocolResponse) -> None:
        if not response.provider_reference:
            raise ValueError("provider_reference required")
        if response.status not in {
            "AUTHORIZED",
            "CAPTURED",
            "DECLINED",
            "FAILED",
            "CANCELLED",
            "TIMEOUT",
            "UNKNOWN",
        }:
            raise ValueError(f"Unexpected sandbox status: {response.status}")

    def map_status(self, response: ProtocolResponse) -> str:
        return response.status

    def send_request(self, definition: ProtocolDefinition, request: ProtocolRequest) -> ProtocolResponse:
        return self.execute(definition, request)

    # Back-compat aliases used by earlier module surface
    def validate(self, definition: ProtocolDefinition, request: ProtocolRequest) -> None:
        self.validate_request(definition, request)

    def prepare(self, definition: ProtocolDefinition, request: ProtocolRequest) -> dict:
        return self.build_request(definition, request)

    def execute(self, definition: ProtocolDefinition, request: ProtocolRequest) -> ProtocolResponse:
        self.validate_request(definition, request)
        built = self.build_request(definition, request)
        reference = f"proto_{definition.code.replace('.', '_')}_{uuid4().hex[:10]}"
        auth = f"AUTH{uuid4().hex[:6].upper()}"

        if request.payment_token.endswith("declined"):
            response = ProtocolResponse(
                status="DECLINED",
                provider_reference=reference,
                authorization_code=None,
                signature_required=False,
                raw={**built, "reason": "sandbox_declined"},
            )
            self.validate_response(response)
            return response

        outcome = definition.sandbox_outcome
        signature_required = (
            outcome == "signature"
            or request.payment_token.endswith("sig")
            or request.payment_token.endswith("signature")
        )

        if outcome in {"pre_auth", "offline_auth"} or signature_required:
            status = "AUTHORIZED"
        elif outcome in {"capture", "force_post", "completion"}:
            status = "CAPTURED"
        else:
            status = "AUTHORIZED"

        if signature_required:
            status = "AUTHORIZED"

        response = ProtocolResponse(
            status=status,
            provider_reference=reference,
            authorization_code=auth,
            signature_required=signature_required,
            raw={
                **built,
                "mode": definition.mode,
                "documented": definition.documented,
            },
        )
        self.validate_response(response)
        return response

    def parse_response(self, payload: dict) -> ProtocolResponse:
        response = ProtocolResponse(
            status=str(payload.get("status") or "AUTHORIZED"),
            provider_reference=str(payload.get("provider_reference") or ""),
            authorization_code=payload.get("authorization_code"),
            signature_required=bool(payload.get("signature_required")),
            raw=payload,
        )
        self.validate_response(response)
        return response


def resolve_sandbox_charge_flags(
    protocol_code: str | None,
    *,
    token: str,
    scenario: str,
) -> tuple[bool, bool]:
    """Return (signature_required, prefer_authorized_not_captured).

    Used by SandboxPaymentGateway so protocol catalog drives sandbox outcomes.
    """
    from app.protocols import get_protocol

    signature = scenario == "signature" or token.endswith("signature") or token.endswith("sig")
    prefer_auth = False
    if protocol_code:
        try:
            definition = get_protocol(protocol_code)
        except KeyError:
            definition = None
        if definition:
            if definition.sandbox_outcome == "signature":
                signature = True
            if definition.sandbox_outcome in {"pre_auth", "offline_auth", "signature"}:
                prefer_auth = True
            if definition.sandbox_outcome in {"capture", "force_post", "completion"} and not signature:
                prefer_auth = False
    if signature:
        prefer_auth = True
    return signature, prefer_auth
