from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import SettlementStatus, TransactionStatus
from app.core.logging import get_logger
from app.crypto.factory import get_exchange_provider
from app.exceptions.base import NotFoundError, SettlementError
from app.models.payment import CryptoSettlement, CryptoTransferLog
from app.repositories.merchant import MerchantWalletRepository
from app.repositories.transaction import SettlementRepository, TransactionRepository
from app.wallet.base import WalletTransferRequest
from app.wallet.factory import get_wallet_provider

logger = get_logger(__name__)


class SettlementEngine:
    """
    Orchestrates post-capture settlement:

    Payment success → validate → fees → exchange quote → wallet transfer → complete

    Card gateways never convert fiat to USDT directly. This engine owns that workflow.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.transactions = TransactionRepository(session)
        self.settlements = SettlementRepository(session)
        self.wallets = MerchantWalletRepository(session)
        self.settings = get_settings()

    def _calculate_fees(self, amount: Decimal) -> tuple[Decimal, Decimal]:
        fee = (amount * Decimal(str(self.settings.platform_fee_percent)) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        net = (amount - fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return fee, net

    async def prepare_and_settle(self, transaction_id: UUID) -> CryptoSettlement:
        transaction = await self.transactions.get_detailed(transaction_id)
        if transaction is None:
            raise NotFoundError("Transaction not found")

        if transaction.status not in {
            TransactionStatus.CAPTURED,
            TransactionStatus.SUCCESS,
            TransactionStatus.SETTLEMENT_PENDING,
            TransactionStatus.SETTLEMENT_PROCESSING,
        }:
            raise SettlementError(
                f"Transaction status '{transaction.status}' is not eligible for settlement"
            )

        existing = await self.settlements.get_by_transaction(transaction_id)
        if existing and existing.status == SettlementStatus.COMPLETED:
            return existing

        wallet = await self.wallets.get_primary(transaction.merchant_id)
        if wallet is None:
            raise SettlementError("Merchant has no primary USDT wallet configured")

        fee, net = self._calculate_fees(transaction.amount)
        previous = transaction.status
        transaction.fees = fee
        transaction.tax = Decimal("0.00")
        transaction.net_amount = net
        transaction.status = TransactionStatus.SETTLEMENT_PROCESSING
        await self.transactions.add_status_log(
            transaction.id,
            from_status=previous,
            to_status=TransactionStatus.SETTLEMENT_PROCESSING,
            note="Settlement engine started",
            actor="settlement_engine",
        )

        exchange = get_exchange_provider()
        usdt_amount, quote = await exchange.convert(net, transaction.currency, "USDT")

        settlement = existing or CryptoSettlement(
            transaction_id=transaction.id,
            merchant_wallet_id=wallet.id,
            fiat_amount=net,
            fiat_currency=transaction.currency,
            usdt_amount=usdt_amount,
            exchange_rate=quote.sell_rate,
            exchange_provider=quote.provider,
            wallet_network=wallet.wallet_network,
            wallet_address=wallet.wallet_address,
            status=SettlementStatus.PROCESSING,
        )
        if existing:
            settlement.fiat_amount = net
            settlement.usdt_amount = usdt_amount
            settlement.exchange_rate = quote.sell_rate
            settlement.exchange_provider = quote.provider
            settlement.status = SettlementStatus.PROCESSING
            settlement.failure_reason = None
        else:
            await self.settlements.add(settlement)

        self.session.add(
            CryptoTransferLog(
                settlement_id=settlement.id,
                action="exchange_quote",
                status="success",
                payload={
                    "rate": str(quote.sell_rate),
                    "provider": quote.provider,
                    "usdt_amount": str(usdt_amount),
                },
            )
        )
        await self.session.flush()

        wallet_provider = get_wallet_provider(wallet.wallet_network)
        transfer = await wallet_provider.transfer(
            WalletTransferRequest(
                to_address=wallet.wallet_address,
                amount=usdt_amount,
                network=wallet.wallet_network,
                currency="USDT",
                memo=f"settlement:{transaction.id}",
                metadata={"transaction_id": str(transaction.id)},
            )
        )

        self.session.add(
            CryptoTransferLog(
                settlement_id=settlement.id,
                action="wallet_transfer",
                status="success" if transfer.success else "failed",
                payload=transfer.raw_response,
                message=transfer.error_message,
            )
        )

        if not transfer.success:
            settlement.status = SettlementStatus.FAILED
            settlement.failure_reason = transfer.error_message
            settlement.retry_count += 1
            transaction.status = TransactionStatus.MANUAL_REVIEW
            await self.transactions.add_status_log(
                transaction.id,
                from_status=TransactionStatus.SETTLEMENT_PROCESSING,
                to_status=TransactionStatus.MANUAL_REVIEW,
                note=transfer.error_message or "Wallet transfer failed",
                actor="settlement_engine",
            )
            await self.session.flush()
            logger.error(
                "settlement_failed",
                transaction_id=str(transaction.id),
                reason=transfer.error_message,
            )
            raise SettlementError(transfer.error_message or "Wallet transfer failed")

        settlement.blockchain_tx_hash = transfer.tx_hash
        settlement.confirmation_count = transfer.confirmation_count
        settlement.status = SettlementStatus.COMPLETED
        transaction.status = TransactionStatus.COMPLETED
        await self.transactions.add_status_log(
            transaction.id,
            from_status=TransactionStatus.SETTLEMENT_PROCESSING,
            to_status=TransactionStatus.COMPLETED,
            note=f"USDT transfer {transfer.tx_hash}",
            actor="settlement_engine",
        )
        await self.session.flush()
        logger.info(
            "settlement_completed",
            transaction_id=str(transaction.id),
            tx_hash=transfer.tx_hash,
            usdt_amount=str(usdt_amount),
        )
        return settlement
