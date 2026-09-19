"""Terminal session service — state machine + PaymentProcessor factory."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import AppException, NotFoundError
from app.payments.terminal_state_machine import (
    AMOUNT_ENTERED,
    APPROVED,
    AUTHORIZING,
    CANCELLED,
    CAPTURED,
    CARD_PRESENTED,
    COMPLETED,
    CREATED,
    DECLINED,
    FAILED,
    PROTOCOL_SELECTED,
    REFUNDED,
    VOIDED,
    assert_terminal_transition,
    transition,
)
from app.processors.factory import get_payment_processor
from app.protocols import get_protocol, validate_protocol_selection
from app.repositories.merchant import MerchantRepository
from app.schemas.terminal import (
    AuthorizeTerminalSessionRequest,
    CreateTerminalSessionRequest,
    RefundTerminalSessionRequest,
    TerminalSessionOut,
)
from app.services.audit_service import AuditService
from app.services.terminal_session_store import (
    TerminalSessionRecord,
    get_terminal_session_store,
    new_session_id,
)


def _to_out(record: TerminalSessionRecord) -> TerminalSessionOut:
    return TerminalSessionOut(
        id=record.id,
        state=record.state,
        amount_minor=record.amount_minor,
        currency=record.currency,
        transaction_type=record.transaction_type,
        protocol_id=record.protocol_id,
        protocol_code=record.protocol_code,
        protocol_label=record.protocol_label,
        sandbox_outcome=record.sandbox_outcome,
        environment=record.environment,
        authorization_code=record.authorization_code,
        processor_reference=record.processor_reference,
        processor_status=record.processor_status,
        processor_message=record.processor_message,
        signature_required=record.signature_required,
        card_brand=record.card_brand,
        card_last4=record.card_last4,
        device_id=record.device_id,
        events=list(record.events),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _append_event(record: TerminalSessionRecord, from_state: str | None, to_state: str, note: str) -> None:
    record.events.append(
        {
            "from": from_state,
            "to": to_state,
            "note": note,
        }
    )


class TerminalSessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.db = session
        self.merchants = MerchantRepository(session)
        self.audit = AuditService(session)
        self.store = get_terminal_session_store()
        self.processor = get_payment_processor()

    async def _merchant_for(self, user_id: UUID):
        merchant = await self.merchants.get_by_owner(user_id)
        if merchant is None:
            raise AppException("Merchant profile required", status_code=403)
        return merchant

    async def create(self, user_id: UUID, payload: CreateTerminalSessionRequest) -> TerminalSessionOut:
        merchant = await self._merchant_for(user_id)
        currency = payload.currency.upper()
        txn_type = payload.transaction_type.upper()

        protocol_id = None
        protocol_code = None
        protocol_label = None
        sandbox_outcome = "capture"
        if payload.protocol_code:
            try:
                definition = validate_protocol_selection(payload.protocol_code, txn_type)
            except (KeyError, ValueError) as exc:
                raise AppException(str(exc), status_code=422) from exc
            protocol_id = definition.selection_id
            protocol_code = definition.code
            protocol_label = definition.display_label
            sandbox_outcome = definition.sandbox_outcome

        record = TerminalSessionRecord(
            id=new_session_id(),
            merchant_id=merchant.id,
            user_id=user_id,
            state=CREATED,
            amount_minor=payload.amount_minor,
            currency=currency,
            transaction_type=txn_type,
            protocol_id=protocol_id,
            protocol_code=protocol_code,
            protocol_label=protocol_label,
            sandbox_outcome=sandbox_outcome,
            device_id=payload.device_id,
            idempotency_key=payload.idempotency_key,
            environment="SANDBOX",
        )
        _append_event(record, None, CREATED, "Session created")

        # Advance to AMOUNT_ENTERED then PROTOCOL_SELECTED when protocol provided.
        prev = record.state
        record.state = transition(prev, AMOUNT_ENTERED)
        _append_event(record, prev, record.state, "Amount entered")
        if protocol_id:
            prev = record.state
            record.state = transition(prev, PROTOCOL_SELECTED)
            _append_event(record, prev, record.state, f"Protocol selected: {protocol_label}")

        record = self.store.create(record)
        await self.audit.record(
            action="terminal_session_created",
            resource_type="terminal_session",
            resource_id=str(record.id),
            actor_user_id=user_id,
            details={
                "amount_minor": record.amount_minor,
                "currency": record.currency,
                "protocol_code": record.protocol_code,
                "state": record.state,
            },
        )
        return _to_out(record)

    async def get(self, user_id: UUID, session_id: UUID) -> TerminalSessionOut:
        merchant = await self._merchant_for(user_id)
        record = self.store.get(session_id)
        if record is None or record.merchant_id != merchant.id:
            raise NotFoundError("Terminal session not found")
        return _to_out(record)

    async def list_sessions(
        self,
        user_id: UUID,
        *,
        status: str | None = None,
        protocol: str | None = None,
        currency: str | None = None,
    ) -> list[TerminalSessionOut]:
        merchant = await self._merchant_for(user_id)
        return [
            _to_out(r)
            for r in self.store.list_for_merchant(
                merchant.id,
                status=status,
                protocol=protocol,
                currency=currency,
            )
        ]

    def _owned(self, user_id: UUID, merchant_id: UUID, session_id: UUID) -> TerminalSessionRecord:
        record = self.store.get(session_id)
        if record is None or record.merchant_id != merchant_id:
            raise NotFoundError("Terminal session not found")
        return record

    async def authorize(
        self, user_id: UUID, session_id: UUID, payload: AuthorizeTerminalSessionRequest
    ) -> TerminalSessionOut:
        merchant = await self._merchant_for(user_id)
        record = self._owned(user_id, merchant.id, session_id)

        if record.state != PROTOCOL_SELECTED:
            # Allow authorize if only amount entered but protocol set on create path missed
            if record.state == AMOUNT_ENTERED and record.protocol_id:
                prev = record.state
                record.state = transition(prev, PROTOCOL_SELECTED)
                _append_event(record, prev, record.state, "Protocol selected before authorize")
            else:
                raise AppException(
                    f"Authorize requires PROTOCOL_SELECTED (was {record.state})",
                    status_code=409,
                )

        token = payload.payment_method_token
        if not token.startswith("pm_"):
            raise AppException("payment_method_token required — never send raw PAN/CVV", status_code=422)

        from app.core.config import get_settings
        from app.protocols.execution import require_protocol_execution

        settings = get_settings()
        require_protocol_execution(
            record.protocol_code,
            environment=settings.payment_environment,
        )

        prev = record.state
        record.state = transition(prev, CARD_PRESENTED)
        _append_event(record, prev, record.state, "Card presented (tokenized)")
        prev = record.state
        record.state = transition(prev, AUTHORIZING)
        _append_event(record, prev, record.state, "Authorizing")

        try:
            result = self.processor.authorize(
                session_id=str(record.id),
                amount_minor=record.amount_minor,
                currency=record.currency,
                sandbox_outcome=record.sandbox_outcome or "capture",
                payment_method_token=token,
                scenario=payload.scenario,
            )
        except ValueError as exc:
            prev = record.state
            record.state = transition(prev, FAILED)
            _append_event(record, prev, record.state, str(exc))
            self.store.save(record)
            raise AppException(str(exc), status_code=422) from exc

        record.payment_method_token = token
        record.processor_reference = result.processor_reference
        record.processor_status = result.status
        record.processor_message = result.message
        record.authorization_code = result.authorization_code
        record.signature_required = result.signature_required
        record.card_brand = result.card_brand
        record.card_last4 = result.card_last4

        if result.status == "APPROVED":
            prev = record.state
            record.state = transition(prev, APPROVED)
            _append_event(record, prev, record.state, result.message or "Approved")
            outcome = record.sandbox_outcome or "capture"
            if outcome in {"pre_auth", "offline_auth", "signature"}:
                pass
            elif outcome == "completion":
                self.processor.complete_authorization(
                    session_id=str(record.id),
                    processor_reference=result.processor_reference,
                    amount_minor=record.amount_minor,
                    currency=record.currency,
                )
                prev = record.state
                record.state = transition(prev, COMPLETED)
                _append_event(record, prev, record.state, "Completion")
            else:
                self.processor.capture(
                    session_id=str(record.id),
                    processor_reference=result.processor_reference,
                    amount_minor=record.amount_minor,
                    currency=record.currency,
                )
                prev = record.state
                record.state = transition(prev, CAPTURED)
                _append_event(record, prev, record.state, "Captured")
                prev = record.state
                record.state = transition(prev, COMPLETED)
                _append_event(record, prev, record.state, "Completed")
        elif result.status == "DECLINED":
            prev = record.state
            record.state = transition(prev, DECLINED)
            _append_event(record, prev, record.state, result.message or "Declined")
        elif result.status == "CANCELLED":
            prev = record.state
            record.state = transition(prev, CANCELLED)
            _append_event(record, prev, record.state, result.message or "Cancelled")
        else:
            prev = record.state
            record.state = transition(prev, FAILED)
            _append_event(record, prev, record.state, result.message or result.status)

        self.store.save(record)
        await self.audit.record(
            action="terminal_session_authorized",
            resource_type="terminal_session",
            resource_id=str(record.id),
            actor_user_id=user_id,
            details={
                "state": record.state,
                "processor_status": record.processor_status,
                "processor_reference": record.processor_reference,
                "authorization_code": record.authorization_code,
            },
        )
        return _to_out(record)

    async def capture(self, user_id: UUID, session_id: UUID) -> TerminalSessionOut:
        merchant = await self._merchant_for(user_id)
        record = self._owned(user_id, merchant.id, session_id)
        if record.state != APPROVED:
            raise AppException(f"Capture requires APPROVED (was {record.state})", status_code=409)
        if not record.processor_reference:
            raise AppException("Missing processor reference", status_code=409)
        self.processor.capture(
            session_id=str(record.id),
            processor_reference=record.processor_reference,
            amount_minor=record.amount_minor,
            currency=record.currency,
        )
        prev = record.state
        record.state = transition(prev, CAPTURED)
        _append_event(record, prev, record.state, "Captured")
        prev = record.state
        record.state = transition(prev, COMPLETED)
        _append_event(record, prev, record.state, "Completed")
        self.store.save(record)
        await self.audit.record(
            action="terminal_session_captured",
            resource_type="terminal_session",
            resource_id=str(record.id),
            actor_user_id=user_id,
            details={"state": record.state},
        )
        return _to_out(record)

    async def void(self, user_id: UUID, session_id: UUID) -> TerminalSessionOut:
        merchant = await self._merchant_for(user_id)
        record = self._owned(user_id, merchant.id, session_id)
        assert_terminal_transition(record.state, VOIDED)
        if record.processor_reference:
            try:
                self.processor.void_transaction(
                    session_id=str(record.id),
                    processor_reference=record.processor_reference,
                )
            except (KeyError, ValueError) as exc:
                raise AppException(str(exc), status_code=409) from exc
        prev = record.state
        record.state = transition(prev, VOIDED)
        _append_event(record, prev, record.state, "Voided")
        self.store.save(record)
        await self.audit.record(
            action="terminal_session_voided",
            resource_type="terminal_session",
            resource_id=str(record.id),
            actor_user_id=user_id,
            details={"state": record.state},
        )
        return _to_out(record)

    async def refund(
        self, user_id: UUID, session_id: UUID, payload: RefundTerminalSessionRequest
    ) -> TerminalSessionOut:
        merchant = await self._merchant_for(user_id)
        record = self._owned(user_id, merchant.id, session_id)
        assert_terminal_transition(record.state, REFUNDED)
        amount = payload.amount_minor or record.amount_minor
        if not record.processor_reference:
            raise AppException("Missing processor reference", status_code=409)
        result = self.processor.refund(
            session_id=str(record.id),
            processor_reference=record.processor_reference,
            amount_minor=amount,
            currency=record.currency,
        )
        prev = record.state
        record.state = transition(prev, REFUNDED)
        record.processor_reference = result.processor_reference
        record.authorization_code = result.authorization_code
        record.processor_message = result.message or payload.reason
        _append_event(record, prev, record.state, result.message or "Refunded")
        self.store.save(record)
        await self.audit.record(
            action="terminal_session_refunded",
            resource_type="terminal_session",
            resource_id=str(record.id),
            actor_user_id=user_id,
            details={"state": record.state, "amount_minor": amount},
        )
        return _to_out(record)

    async def cancel(self, user_id: UUID, session_id: UUID) -> TerminalSessionOut:
        merchant = await self._merchant_for(user_id)
        record = self._owned(user_id, merchant.id, session_id)
        assert_terminal_transition(record.state, CANCELLED)
        prev = record.state
        record.state = transition(prev, CANCELLED)
        _append_event(record, prev, record.state, "Cancelled by operator")
        self.store.save(record)
        await self.audit.record(
            action="terminal_session_cancelled",
            resource_type="terminal_session",
            resource_id=str(record.id),
            actor_user_id=user_id,
            details={"state": record.state},
        )
        return _to_out(record)

    @staticmethod
    def select_protocol_only(session_id: UUID, merchant_id: UUID, protocol_code: str) -> TerminalSessionOut:
        """Helper for attaching protocol after create without authorize."""
        store = get_terminal_session_store()
        record = store.get(session_id)
        if record is None or record.merchant_id != merchant_id:
            raise NotFoundError("Terminal session not found")
        definition = get_protocol(protocol_code)
        if record.state != AMOUNT_ENTERED:
            raise AppException(f"Protocol select requires AMOUNT_ENTERED (was {record.state})", status_code=409)
        prev = record.state
        record.state = transition(prev, PROTOCOL_SELECTED)
        record.protocol_id = definition.selection_id
        record.protocol_code = definition.code
        record.protocol_label = definition.display_label
        record.sandbox_outcome = definition.sandbox_outcome
        _append_event(record, prev, record.state, f"Protocol selected: {definition.display_label}")
        store.save(record)
        return _to_out(record)
