from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import MerchantStatus, TransactionStatus
from app.core.logging import get_logger
from app.exceptions.base import AppException, ConflictError, ForbiddenError, NotFoundError, PaymentError
from app.models.merchant import MerchantProfile, MerchantWallet
from app.models.payment import PaymentAttempt, Receipt, Transaction
from app.payments.base import PaymentRequest, RefundRequest
from app.payments.factory import get_payment_gateway
from app.payments.money import from_minor_units, to_minor_units
from app.payments.state_machine import assert_transition
from app.protocols import get_protocol, list_protocols
from app.repositories.merchant import MerchantRepository, MerchantWalletRepository
from app.repositories.transaction import (
    PaymentAttemptRepository,
    PaymentGatewayRepository,
    ReceiptRepository,
    TransactionRepository,
)
from app.schemas.merchant import MerchantCreate, MerchantOut, WalletCreate, WalletOut
from app.schemas.payment import (
    CompleteSignatureRequest,
    CreatePaymentRequest,
    PaymentOut,
    ProtocolOut,
    ReceiptOut,
    RefundPaymentRequest,
    SandboxTokenOut,
    SandboxTokenRequest,
    TransactionListOut,
)
from app.services.audit_service import AuditService
from app.settlement.engine import SettlementEngine

logger = get_logger(__name__)


def _payment_out(transaction: Transaction) -> PaymentOut:
    base = PaymentOut.model_validate(transaction)
    extra = transaction.extra_data or {}
    return base.model_copy(
        update={
            "signature_required": bool(extra.get("signature_required")),
            "authorization_code": extra.get("authorization_code"),
            "payment_mode": extra.get("payment_mode"),
            "protocol_code": extra.get("protocol_code"),
            "card_last4": extra.get("card_last4"),
            "amount_minor": extra.get("amount_minor"),
        }
    )


class MerchantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.merchants = MerchantRepository(session)
        self.wallets = MerchantWalletRepository(session)

    async def create_merchant(self, owner_user_id: UUID, payload: MerchantCreate) -> MerchantOut:
        existing = await self.merchants.get_by_owner(owner_user_id)
        if existing:
            raise ConflictError("Merchant profile already exists for this user")

        merchant = MerchantProfile(
            owner_user_id=owner_user_id,
            company_name=payload.company_name,
            commercial_registration=payload.commercial_registration,
            tax_number=payload.tax_number,
            country=payload.country,
            city=payload.city,
            address=payload.address,
            website=payload.website,
            email=payload.email.lower(),
            phone=payload.phone,
            industry=payload.industry,
            status=MerchantStatus.ACTIVE,
        )
        merchant = await self.merchants.add(merchant)
        return MerchantOut.model_validate(merchant)

    async def get_my_merchant(self, owner_user_id: UUID) -> MerchantOut:
        merchant = await self.merchants.get_by_owner(owner_user_id)
        if merchant is None:
            raise NotFoundError("Merchant profile not found")
        return MerchantOut.model_validate(merchant)

    async def add_wallet(self, owner_user_id: UUID, payload: WalletCreate) -> WalletOut:
        merchant = await self.merchants.get_by_owner(owner_user_id)
        if merchant is None:
            raise NotFoundError("Merchant profile not found")

        if payload.is_primary:
            for wallet in await self.wallets.list_for_merchant(merchant.id):
                wallet.is_primary = False

        wallet = MerchantWallet(
            merchant_id=merchant.id,
            wallet_address=payload.wallet_address,
            wallet_provider=payload.wallet_provider,
            wallet_network=payload.wallet_network,
            is_primary=payload.is_primary,
        )
        wallet = await self.wallets.add(wallet)
        return WalletOut.model_validate(wallet)

    async def list_wallets(self, owner_user_id: UUID) -> list[WalletOut]:
        merchant = await self.merchants.get_by_owner(owner_user_id)
        if merchant is None:
            raise NotFoundError("Merchant profile not found")
        wallets = await self.wallets.list_for_merchant(merchant.id)
        return [WalletOut.model_validate(item) for item in wallets]


class PaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.merchants = MerchantRepository(session)
        self.transactions = TransactionRepository(session)
        self.attempts = PaymentAttemptRepository(session)
        self.gateways = PaymentGatewayRepository(session)
        self.receipts = ReceiptRepository(session)
        self.settings = get_settings()

    async def _resolve_merchant_for_user(self, user_id: UUID) -> MerchantProfile:
        merchant = await self.merchants.get_by_owner(user_id)
        if merchant is None:
            raise NotFoundError("Merchant profile not found")
        if merchant.status != MerchantStatus.ACTIVE:
            raise ForbiddenError("Merchant account is not active")
        return merchant

    async def create_payment(self, user_id: UUID, payload: CreatePaymentRequest) -> PaymentOut:
        currency = payload.currency.upper()
        if currency not in self.settings.supported_currencies:
            raise AppException(
                f"Currency {currency} is not enabled. Allowed: {', '.join(sorted(self.settings.supported_currencies))}",
                status_code=422,
            )
        merchant = await self._resolve_merchant_for_user(user_id)
        audit = AuditService(self.session)

        # Resolve amount from minor units when provided (preferred).
        if payload.amount_minor is not None:
            amount = from_minor_units(payload.amount_minor, currency)
            amount_minor = payload.amount_minor
        else:
            assert payload.amount is not None
            amount = payload.amount
            amount_minor = to_minor_units(amount, currency)

        # Idempotency: reuse merchant_reference (or explicit key as reference).
        reference = payload.idempotency_key or payload.merchant_reference
        existing = await self.transactions.get_by_merchant_reference(merchant.id, reference)
        if existing is None and payload.idempotency_key and payload.idempotency_key != payload.merchant_reference:
            existing = await self.transactions.get_by_merchant_reference(
                merchant.id, payload.merchant_reference
            )
        if existing:
            detailed = await self.transactions.get_detailed(existing.id)
            assert detailed is not None
            return _payment_out(detailed)

        if payload.protocol_code:
            try:
                protocol_def = get_protocol(payload.protocol_code)
            except KeyError as exc:
                raise AppException(str(exc), status_code=422) from exc
        else:
            protocol_def = None

        if payload.payment_mode == "offline_test" and (payload.gateway_provider or "sandbox") != "sandbox":
            raise AppException(
                "offline_test mode is sandbox-only — no real processor charges",
                status_code=422,
            )

        gateway = get_payment_gateway(payload.gateway_provider)
        gateway_row = await self.gateways.get_by_provider(gateway.provider_name)

        assert_transition(None, TransactionStatus.PROCESSING)

        protocol_selection = protocol_def.selection_id if protocol_def else payload.protocol_code
        protocol_canonical = protocol_def.code if protocol_def else payload.protocol_code

        transaction = Transaction(
            merchant_id=merchant.id,
            gateway_id=gateway_row.id if gateway_row else None,
            amount=amount,
            currency=currency,
            merchant_reference=reference,
            status=TransactionStatus.PROCESSING,
            fees=Decimal("0.00"),
            tax=Decimal("0.00"),
            net_amount=Decimal("0.00"),
            extra_data={
                "description": payload.description,
                "gateway_provider": gateway.provider_name,
                "payment_mode": payload.payment_mode,
                "protocol_code": protocol_selection,
                "protocol_canonical": protocol_canonical,
                "protocol_label": protocol_def.display_label if protocol_def else None,
                "protocol_connectivity": protocol_def.connectivity if protocol_def else None,
                "amount_minor": amount_minor,
                "idempotency_key": payload.idempotency_key or reference,
                # Never store PAN/CVV — token only.
                "payment_method_token": payload.payment_method_token,
            },
        )
        transaction = await self.transactions.add(transaction)
        await self.transactions.add_status_log(
            transaction.id,
            from_status=None,
            to_status=TransactionStatus.PROCESSING,
            note="Payment initiated from POS",
            actor="payment_service",
        )
        await audit.record(
            action="payment_initiated",
            resource_type="transaction",
            resource_id=str(transaction.id),
            actor_user_id=user_id,
            details={
                "amount_minor": amount_minor,
                "currency": currency,
                "payment_mode": payload.payment_mode,
                "protocol_code": payload.protocol_code,
                "gateway": gateway.provider_name,
            },
        )

        result = await gateway.charge(
            PaymentRequest(
                amount=amount,
                currency=currency,
                merchant_reference=reference,
                description=payload.description or f"Payment {reference}",
                metadata={
                    "transaction_id": str(transaction.id),
                    "merchant_id": str(merchant.id),
                    "payment_method_token": payload.payment_method_token,
                    "payment_token": payload.payment_method_token,
                    "sandbox_scenario": payload.sandbox_scenario,
                    "protocol_code": protocol_selection,
                    "payment_mode": payload.payment_mode,
                },
            )
        )

        attempt = PaymentAttempt(
            transaction_id=transaction.id,
            gateway_provider=gateway.provider_name,
            attempt_number=1,
            status=result.status,
            gateway_response={
                k: v
                for k, v in (result.raw_response or {}).items()
                if k.lower() not in {"pan", "cvv", "cvc", "card_number"}
            },
            error_message=result.error_message,
        )
        await self.attempts.add(attempt)

        transaction.gateway_reference = result.gateway_reference
        transaction.payment_method = result.payment_method
        transaction.payment_date = datetime.now(UTC)
        extra = dict(transaction.extra_data or {})
        extra["authorization_code"] = result.authorization_code
        extra["signature_required"] = result.signature_required
        extra["card_last4"] = result.card_last4
        if result.payment_method_token:
            extra["payment_method_token"] = result.payment_method_token
        transaction.extra_data = extra

        if not result.success:
            assert_transition(TransactionStatus.PROCESSING, TransactionStatus.FAILED)
            transaction.status = TransactionStatus.FAILED
            transaction.failure_reason = result.error_message
            await self.transactions.add_status_log(
                transaction.id,
                from_status=TransactionStatus.PROCESSING,
                to_status=TransactionStatus.FAILED,
                note=result.error_message,
                actor="payment_gateway",
            )
            await audit.record(
                action="payment_declined",
                resource_type="transaction",
                resource_id=str(transaction.id),
                actor_user_id=user_id,
                details={"reason": result.error_message},
            )
            await self.session.flush()
            await self.session.commit()
            raise PaymentError(
                result.error_message or "Payment failed",
                data=_payment_out(transaction).model_dump(mode="json"),
            )

        if result.signature_required:
            assert_transition(TransactionStatus.PROCESSING, TransactionStatus.AUTHORIZED)
            transaction.status = TransactionStatus.AUTHORIZED
            await self.transactions.add_status_log(
                transaction.id,
                from_status=TransactionStatus.PROCESSING,
                to_status=TransactionStatus.AUTHORIZED,
                note="Signature required before capture",
                actor="payment_gateway",
            )
            await audit.record(
                action="signature_required",
                resource_type="transaction",
                resource_id=str(transaction.id),
                actor_user_id=user_id,
                details={"authorization_code": result.authorization_code},
            )
            await self.session.flush()
            await self.session.commit()
            detailed = await self.transactions.get_detailed(transaction.id)
            assert detailed is not None
            return _payment_out(detailed)

        assert_transition(TransactionStatus.PROCESSING, TransactionStatus.CAPTURED)
        transaction.status = TransactionStatus.CAPTURED
        transaction.receipt_number = self._build_receipt_number()
        await self.transactions.add_status_log(
            transaction.id,
            from_status=TransactionStatus.PROCESSING,
            to_status=TransactionStatus.CAPTURED,
            note="Card payment captured",
            actor="payment_gateway",
        )
        await audit.record(
            action="payment_captured",
            resource_type="transaction",
            resource_id=str(transaction.id),
            actor_user_id=user_id,
            details={"gateway_reference": result.gateway_reference},
        )

        await self._attach_receipt(transaction, merchant, gateway.provider_name)
        await self.session.flush()
        await self._try_settle(transaction)

        detailed = await self.transactions.get_detailed(transaction.id)
        assert detailed is not None
        return _payment_out(detailed)

    async def complete_signature(
        self,
        user_id: UUID,
        transaction_id: UUID,
        payload: CompleteSignatureRequest,
    ) -> PaymentOut:
        merchant = await self._resolve_merchant_for_user(user_id)
        transaction = await self.transactions.get_detailed(transaction_id)
        if transaction is None or transaction.merchant_id != merchant.id:
            raise NotFoundError("Transaction not found")
        if transaction.status != TransactionStatus.AUTHORIZED:
            raise AppException("Transaction is not awaiting signature", status_code=409)
        if not payload.acknowledged:
            raise AppException("Signature must be acknowledged", status_code=422)

        assert_transition(TransactionStatus.AUTHORIZED, TransactionStatus.CAPTURED)
        extra = dict(transaction.extra_data or {})
        extra["signature_required"] = False
        extra["signature_completed"] = True
        # Store only a truncated fingerprint of the signature blob — not card data.
        if payload.signature_data_url:
            extra["signature_present"] = True
            extra["signature_bytes_approx"] = min(len(payload.signature_data_url), 200_000)
        transaction.extra_data = extra
        transaction.status = TransactionStatus.CAPTURED
        transaction.receipt_number = transaction.receipt_number or self._build_receipt_number()
        await self.transactions.add_status_log(
            transaction.id,
            from_status=TransactionStatus.AUTHORIZED,
            to_status=TransactionStatus.CAPTURED,
            note="Signature completed; payment captured",
            actor="pos_signature",
        )
        await AuditService(self.session).record(
            action="signature_completed",
            resource_type="transaction",
            resource_id=str(transaction.id),
            actor_user_id=user_id,
            details={"signature_present": bool(payload.signature_data_url)},
        )
        gateway_name = (transaction.extra_data or {}).get("gateway_provider") or "sandbox"
        if transaction.receipt is None:
            await self._attach_receipt(transaction, merchant, gateway_name)
        await self.session.flush()
        await self._try_settle(transaction)
        detailed = await self.transactions.get_detailed(transaction.id)
        assert detailed is not None
        return _payment_out(detailed)

    async def cancel_payment(self, user_id: UUID, transaction_id: UUID) -> PaymentOut:
        merchant = await self._resolve_merchant_for_user(user_id)
        transaction = await self.transactions.get_detailed(transaction_id)
        if transaction is None or transaction.merchant_id != merchant.id:
            raise NotFoundError("Transaction not found")
        assert_transition(transaction.status, TransactionStatus.CANCELLED)
        previous = transaction.status
        transaction.status = TransactionStatus.CANCELLED
        await self.transactions.add_status_log(
            transaction.id,
            from_status=previous,
            to_status=TransactionStatus.CANCELLED,
            note="Cancelled by merchant",
            actor="payment_service",
        )
        await AuditService(self.session).record(
            action="payment_cancelled",
            resource_type="transaction",
            resource_id=str(transaction.id),
            actor_user_id=user_id,
        )
        await self.session.flush()
        await self.session.commit()
        return _payment_out(transaction)

    @staticmethod
    def issue_sandbox_token(payload: SandboxTokenRequest) -> SandboxTokenOut:
        """Map documented TEST PANs to tokens — PAN is never persisted."""
        mapping = {
            "4111111111111111": ("pm_test_visa_success", "success", "1111"),
            "4000000000000002": ("pm_test_visa_declined", "declined", "0002"),
            "4111111111111111_sig": ("pm_test_visa_signature", "signature", "1111"),
        }
        token, scenario, last4 = mapping[payload.test_pan_hint]
        return SandboxTokenOut(payment_method_token=token, scenario=scenario, card_last4=last4)

    @staticmethod
    def list_pos_protocols(
        mode: str | None = None,
        family: str | None = None,
        transaction_type: str | None = None,
    ) -> list[ProtocolOut]:
        return [
            ProtocolOut(
                selection_id=item.selection_id,
                code=item.code,
                name=item.name,
                display_label=item.display_label,
                description=item.description,
                mode=item.mode,
                connectivity=item.connectivity,
                sandbox_outcome=item.sandbox_outcome,
                digit_group=item.digit_group,
                family=item.family,
                version=item.version,
                enabled=item.enabled,
                documented=item.documented,
                sandbox_only=item.sandbox_only,
                requires_online_authorization=item.requires_online_authorization,
                authorization_mode=item.authorization_mode,
                supported_transaction_types=list(item.supported_transaction_types),
                allows_manual_entry=item.allows_manual_entry,
                signature_likely=item.signature_likely,
                ui_environment_label=item.ui_environment_label,
            )
            for item in list_protocols(mode=mode, family=family, transaction_type=transaction_type)
        ]

    async def _attach_receipt(
        self, transaction: Transaction, merchant: MerchantProfile, gateway_name: str
    ) -> Receipt:
        extra = transaction.extra_data or {}
        receipt = Receipt(
            transaction_id=transaction.id,
            receipt_number=transaction.receipt_number or self._build_receipt_number(),
            merchant_name=merchant.company_name,
            amount=transaction.amount,
            currency=transaction.currency,
            gateway=gateway_name,
            status=transaction.status,
            printable_payload={
                "receipt_number": transaction.receipt_number,
                "merchant": merchant.company_name,
                "vat_number": merchant.tax_number or "",
                "amount": str(transaction.amount),
                "amount_minor": extra.get("amount_minor"),
                "currency": transaction.currency,
                "gateway_reference": transaction.gateway_reference,
                "authorization_code": extra.get("authorization_code"),
                "payment_method": transaction.payment_method,
                "card_last4": extra.get("card_last4"),
                "status": transaction.status,
                "payment_mode": extra.get("payment_mode"),
                "protocol_code": extra.get("protocol_code"),
                "protocol_canonical": extra.get("protocol_canonical"),
                "protocol_label": extra.get("protocol_label"),
                "paid_at": transaction.payment_date.isoformat() if transaction.payment_date else None,
            },
        )
        if not transaction.receipt_number:
            transaction.receipt_number = receipt.receipt_number
        await self.receipts.add(receipt)
        return receipt

    async def _try_settle(self, transaction: Transaction) -> None:
        try:
            engine = SettlementEngine(self.session)
            await engine.prepare_and_settle(transaction.id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("settlement_enqueue_failed", error=str(exc))
            assert_transition(TransactionStatus.CAPTURED, TransactionStatus.SETTLEMENT_PENDING)
            transaction.status = TransactionStatus.SETTLEMENT_PENDING
            await self.transactions.add_status_log(
                transaction.id,
                from_status=TransactionStatus.CAPTURED,
                to_status=TransactionStatus.SETTLEMENT_PENDING,
                note="Settlement deferred for retry",
                actor="payment_service",
            )
            try:
                from app.tasks.settlement_tasks import settle_transaction

                settle_transaction.delay(str(transaction.id))
            except Exception:  # noqa: BLE001
                logger.warning("celery_unavailable_settlement_pending", transaction_id=str(transaction.id))

    async def get_payment(self, user_id: UUID, transaction_id: UUID) -> PaymentOut:
        merchant = await self._resolve_merchant_for_user(user_id)
        transaction = await self.transactions.get_detailed(transaction_id)
        if transaction is None or transaction.merchant_id != merchant.id:
            raise NotFoundError("Transaction not found")
        return _payment_out(transaction)

    async def list_payments(
        self,
        user_id: UUID,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> TransactionListOut:
        merchant = await self._resolve_merchant_for_user(user_id)
        offset = (page - 1) * page_size
        items, total = await self.transactions.list_for_merchant(
            merchant.id, status=status, offset=offset, limit=page_size
        )
        return TransactionListOut(
            items=[_payment_out(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_receipt(self, user_id: UUID, transaction_id: UUID) -> ReceiptOut:
        merchant = await self._resolve_merchant_for_user(user_id)
        transaction = await self.transactions.get_detailed(transaction_id)
        if transaction is None or transaction.merchant_id != merchant.id:
            raise NotFoundError("Transaction not found")
        if transaction.receipt is None:
            raise NotFoundError("Receipt not found")
        return ReceiptOut.model_validate(transaction.receipt)

    async def refund_payment(
        self,
        user_id: UUID,
        transaction_id: UUID,
        payload: RefundPaymentRequest,
    ) -> PaymentOut:
        merchant = await self._resolve_merchant_for_user(user_id)
        transaction = await self.transactions.get_detailed(transaction_id)
        if transaction is None or transaction.merchant_id != merchant.id:
            raise NotFoundError("Transaction not found")
        refundable = {
            TransactionStatus.CAPTURED,
            TransactionStatus.SUCCESS,
            TransactionStatus.SETTLEMENT_COMPLETE,
            TransactionStatus.SETTLEMENT_PENDING,
            TransactionStatus.COMPLETED,
        }
        if transaction.status not in refundable:
            raise AppException(
                f"Transaction status '{transaction.status}' cannot be refunded",
                status_code=409,
            )
        if not transaction.gateway_reference:
            raise AppException("Missing gateway reference for refund", status_code=409)

        amount = payload.amount or transaction.amount
        extra = transaction.extra_data if isinstance(transaction.extra_data, dict) else {}
        gateway = get_payment_gateway(str(extra.get("gateway_provider") or self.settings.default_payment_gateway))

        result = await gateway.refund(
            RefundRequest(
                gateway_reference=transaction.gateway_reference,
                amount=amount,
                currency=transaction.currency,
                reason=payload.reason,
            )
        )
        if not result.success:
            raise PaymentError(result.error_message or "Refund failed", data=result.raw_response)

        previous = transaction.status
        transaction.status = TransactionStatus.REFUNDED
        transaction.failure_reason = payload.reason
        await self.transactions.add_status_log(
            transaction.id,
            from_status=previous,
            to_status=TransactionStatus.REFUNDED,
            note=payload.reason or result.refund_reference,
            actor="payment_service",
        )
        await self.session.flush()
        detailed = await self.transactions.get_detailed(transaction.id)
        assert detailed is not None
        return _payment_out(detailed)

    async def handle_nowpayments_webhook(self, headers: dict[str, str], payload: dict) -> dict:
        gateway = get_payment_gateway("nowpayments")
        result = await gateway.verify_callback(headers, payload)
        order_id = str(payload.get("order_id") or "")
        reference = result.gateway_reference
        transaction = None
        if order_id:
            transaction = await self.transactions.get_by_merchant_reference_for_any_merchant(order_id)
        if transaction is None and reference:
            transaction = await self.transactions.get_by_gateway_reference(reference)
        if transaction is None:
            return {
                "accepted": True,
                "matched": False,
                "gateway_reference": reference,
                "order_id": order_id,
            }
        if result.success and transaction.status in {
            TransactionStatus.FAILED,
            TransactionStatus.PROCESSING,
            TransactionStatus.PENDING,
        }:
            transaction.status = TransactionStatus.CAPTURED
            if not transaction.receipt_number:
                transaction.receipt_number = self._build_receipt_number()
        elif not result.success and transaction.status in {
            TransactionStatus.PROCESSING,
            TransactionStatus.PENDING,
        }:
            transaction.status = TransactionStatus.FAILED
            transaction.failure_reason = result.error_message
        await self.session.flush()
        return {"accepted": True, "matched": True, "transaction_id": str(transaction.id)}

    async def handle_moyasar_webhook(self, headers: dict[str, str], payload: dict) -> dict:
        gateway = get_payment_gateway("moyasar")
        result = await gateway.verify_callback(headers, payload)
        reference = result.gateway_reference
        if not reference:
            return {"accepted": True, "matched": False}
        transaction = await self.transactions.get_by_gateway_reference(reference)
        if transaction is None:
            return {"accepted": True, "matched": False, "gateway_reference": reference}
        if result.success and transaction.status == TransactionStatus.FAILED:
            transaction.status = TransactionStatus.CAPTURED
        elif not result.success and transaction.status in {
            TransactionStatus.PROCESSING,
            TransactionStatus.PENDING,
        }:
            transaction.status = TransactionStatus.FAILED
            transaction.failure_reason = result.error_message
        await self.session.flush()
        return {"accepted": True, "matched": True, "transaction_id": str(transaction.id)}

    @staticmethod
    def _build_receipt_number() -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        return f"RCP-{stamp}-{uuid4().hex[:8].upper()}"
