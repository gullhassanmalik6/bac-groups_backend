from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payment import (
    CryptoSettlement,
    PaymentAttempt,
    PaymentCallback,
    PaymentGateway,
    Receipt,
    Transaction,
    TransactionStatusLog,
)
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    model = Transaction

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    def _with_relations(self) -> Select[tuple[Transaction]]:
        return self._base_query().options(
            selectinload(Transaction.receipt),
            selectinload(Transaction.settlement),
            selectinload(Transaction.status_logs),
            selectinload(Transaction.payment_attempts),
        )

    async def get_detailed(self, transaction_id: UUID) -> Transaction | None:
        result = await self.session.execute(
            self._with_relations().where(Transaction.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def get_by_merchant_reference(
        self, merchant_id: UUID, merchant_reference: str
    ) -> Transaction | None:
        result = await self.session.execute(
            self._base_query().where(
                Transaction.merchant_id == merchant_id,
                Transaction.merchant_reference == merchant_reference,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_merchant_reference_for_any_merchant(
        self, merchant_reference: str
    ) -> Transaction | None:
        result = await self.session.execute(
            self._with_relations().where(Transaction.merchant_reference == merchant_reference)
        )
        return result.scalar_one_or_none()

    async def get_by_gateway_reference(self, gateway_reference: str) -> Transaction | None:
        result = await self.session.execute(
            self._with_relations().where(Transaction.gateway_reference == gateway_reference)
        )
        return result.scalar_one_or_none()

    async def list_for_merchant(
        self,
        merchant_id: UUID,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Transaction], int]:
        filters = [Transaction.merchant_id == merchant_id, Transaction.deleted_at.is_(None)]
        if status:
            filters.append(Transaction.status == status)

        count_result = await self.session.execute(
            select(func.count()).select_from(Transaction).where(and_(*filters))
        )
        total = int(count_result.scalar_one())

        result = await self.session.execute(
            select(Transaction)
            .where(and_(*filters))
            .order_by(Transaction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def add_status_log(
        self,
        transaction_id: UUID,
        *,
        from_status: str | None,
        to_status: str,
        note: str | None = None,
        actor: str | None = None,
    ) -> TransactionStatusLog:
        log = TransactionStatusLog(
            transaction_id=transaction_id,
            from_status=from_status,
            to_status=to_status,
            note=note,
            actor=actor,
        )
        self.session.add(log)
        await self.session.flush()
        return log


class PaymentGatewayRepository(BaseRepository[PaymentGateway]):
    model = PaymentGateway

    async def get_by_provider(self, provider: str) -> PaymentGateway | None:
        result = await self.session.execute(
            self._base_query().where(PaymentGateway.provider == provider)
        )
        return result.scalar_one_or_none()


class PaymentAttemptRepository(BaseRepository[PaymentAttempt]):
    model = PaymentAttempt


class PaymentCallbackRepository(BaseRepository[PaymentCallback]):
    model = PaymentCallback


class ReceiptRepository(BaseRepository[Receipt]):
    model = Receipt

    async def get_by_transaction(self, transaction_id: UUID) -> Receipt | None:
        result = await self.session.execute(
            self._base_query().where(Receipt.transaction_id == transaction_id)
        )
        return result.scalar_one_or_none()


class SettlementRepository(BaseRepository[CryptoSettlement]):
    model = CryptoSettlement

    async def get_by_transaction(self, transaction_id: UUID) -> CryptoSettlement | None:
        result = await self.session.execute(
            self._base_query()
            .options(selectinload(CryptoSettlement.transfer_logs))
            .where(CryptoSettlement.transaction_id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def list_retryable(self, *, limit: int = 50) -> list[CryptoSettlement]:
        result = await self.session.execute(
            self._base_query()
            .where(CryptoSettlement.status.in_(["failed", "retrying", "pending"]))
            .order_by(CryptoSettlement.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
