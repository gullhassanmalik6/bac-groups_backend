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
from app.repositories.merchant import MerchantRepository, MerchantWalletRepository
from app.repositories.transaction import (
    PaymentAttemptRepository,
    PaymentGatewayRepository,
    ReceiptRepository,
    TransactionRepository,
)
from app.schemas.merchant import MerchantCreate, MerchantOut, WalletCreate, WalletOut
from app.schemas.payment import (
    CreatePaymentRequest,
    PaymentOut,
    ReceiptOut,
    RefundPaymentRequest,
    TransactionListOut,
)
from app.settlement.engine import SettlementEngine

logger = get_logger(__name__)


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

        duplicate = await self.transactions.get_by_merchant_reference(
            merchant.id, payload.merchant_reference
        )
        if duplicate:
            raise ConflictError("merchant_reference must be unique per merchant")

        gateway = get_payment_gateway(payload.gateway_provider)
        gateway_row = await self.gateways.get_by_provider(gateway.provider_name)

        transaction = Transaction(
            merchant_id=merchant.id,
            gateway_id=gateway_row.id if gateway_row else None,
            amount=payload.amount,
            currency=currency,
            merchant_reference=payload.merchant_reference,
            status=TransactionStatus.PROCESSING,
            fees=Decimal("0.00"),
            tax=Decimal("0.00"),
            net_amount=Decimal("0.00"),
            extra_data={
                "description": payload.description,
                "gateway_provider": gateway.provider_name,
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

        result = await gateway.charge(
            PaymentRequest(
                amount=payload.amount,
                currency=currency,
                merchant_reference=payload.merchant_reference,
                description=payload.description or f"Payment {payload.merchant_reference}",
                metadata={"transaction_id": str(transaction.id), "merchant_id": str(merchant.id)},
            )
        )

        attempt = PaymentAttempt(
            transaction_id=transaction.id,
            gateway_provider=gateway.provider_name,
            attempt_number=1,
            status=result.status,
            gateway_response=result.raw_response,
            error_message=result.error_message,
        )
        await self.attempts.add(attempt)

        transaction.gateway_reference = result.gateway_reference
        transaction.payment_method = result.payment_method
        transaction.payment_date = datetime.now(UTC)

        if not result.success:
            transaction.status = TransactionStatus.FAILED
            transaction.failure_reason = result.error_message
            await self.transactions.add_status_log(
                transaction.id,
                from_status=TransactionStatus.PROCESSING,
                to_status=TransactionStatus.FAILED,
                note=result.error_message,
                actor="payment_gateway",
            )
            await self.session.flush()
            await self.session.commit()
            raise PaymentError(
                result.error_message or "Payment failed",
                data=PaymentOut.model_validate(transaction).model_dump(mode="json"),
            )

        transaction.status = TransactionStatus.CAPTURED
        transaction.receipt_number = self._build_receipt_number()
        await self.transactions.add_status_log(
            transaction.id,
            from_status=TransactionStatus.PROCESSING,
            to_status=TransactionStatus.CAPTURED,
            note="Card payment captured",
            actor="payment_gateway",
        )

        receipt = Receipt(
            transaction_id=transaction.id,
            receipt_number=transaction.receipt_number,
            merchant_name=merchant.company_name,
            amount=transaction.amount,
            currency=transaction.currency,
            gateway=gateway.provider_name,
            status=transaction.status,
            printable_payload={
                "receipt_number": transaction.receipt_number,
                "merchant": merchant.company_name,
                "vat_number": merchant.tax_number or "",
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "gateway_reference": transaction.gateway_reference,
                "payment_method": transaction.payment_method,
                "status": transaction.status,
                "paid_at": transaction.payment_date.isoformat() if transaction.payment_date else None,
            },
        )
        await self.receipts.add(receipt)
        await self.session.flush()

        # Settlement is asynchronous in production (Celery). In-process for reliability when broker is down.
        try:
            engine = SettlementEngine(self.session)
            await engine.prepare_and_settle(transaction.id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("settlement_enqueue_failed", error=str(exc))
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

        detailed = await self.transactions.get_detailed(transaction.id)
        assert detailed is not None
        return PaymentOut.model_validate(detailed)

    async def get_payment(self, user_id: UUID, transaction_id: UUID) -> PaymentOut:
        merchant = await self._resolve_merchant_for_user(user_id)
        transaction = await self.transactions.get_detailed(transaction_id)
        if transaction is None or transaction.merchant_id != merchant.id:
            raise NotFoundError("Transaction not found")
        return PaymentOut.model_validate(transaction)

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
            items=[PaymentOut.model_validate(item) for item in items],
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
        return PaymentOut.model_validate(detailed)

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
