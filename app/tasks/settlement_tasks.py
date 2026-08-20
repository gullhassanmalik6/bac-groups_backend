import asyncio
from uuid import UUID

from app.core.logging import get_logger
from app.database.session import AsyncSessionLocal
from app.settlement.engine import SettlementEngine
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


async def _settle(transaction_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            engine = SettlementEngine(session)
            settlement = await engine.prepare_and_settle(UUID(transaction_id))
            await session.commit()
            return {
                "transaction_id": transaction_id,
                "settlement_id": str(settlement.id),
                "status": settlement.status,
                "tx_hash": settlement.blockchain_tx_hash,
            }
        except Exception:
            await session.rollback()
            raise


@celery_app.task(
    name="settlement.settle_transaction",
    bind=True,
    max_retries=5,
    default_retry_delay=30,
)
def settle_transaction(self, transaction_id: str) -> dict:  # noqa: ANN001
    try:
        return asyncio.run(_settle(transaction_id))
    except Exception as exc:  # noqa: BLE001
        logger.exception("celery_settlement_failed", transaction_id=transaction_id, error=str(exc))
        raise self.retry(exc=exc) from exc
