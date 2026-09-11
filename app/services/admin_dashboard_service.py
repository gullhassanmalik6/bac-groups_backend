"""Admin dashboard analytics — terminal sessions + DB payments."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.merchant import DeviceInformation, SunmiDevice
from app.models.payment import Transaction
from app.repositories.merchant import MerchantRepository
from app.repositories.transaction import SettlementRepository, TransactionRepository
from app.services.terminal_session_store import get_terminal_session_store


# Map terminal + legacy payment statuses into dashboard buckets.
_APPROVED = {
    "APPROVED",
    "CAPTURED",
    "COMPLETED",
    "success",
    "paid",
    "captured",
    "settlement_complete",
    "authorized",
}
_DECLINED = {"DECLINED", "declined", "failed"}
_REFUNDED = {"REFUNDED", "refunded", "partially_refunded"}
_VOIDED = {"VOIDED", "voided", "cancelled", "CANCELLED"}
_PENDING = {
    "PENDING",
    "pending",
    "processing",
    "CREATED",
    "AMOUNT_ENTERED",
    "PROTOCOL_SELECTED",
    "CARD_PRESENTED",
    "AUTHORIZING",
}


class DayPoint(BaseModel):
    date: str
    count: int = 0
    volume: float = 0.0


class NamedCount(BaseModel):
    name: str
    count: int


class DeviceStatusRow(BaseModel):
    id: str
    serial_number: str
    model: str
    manufacturer: str | None = None
    connectivity_status: str = "OFFLINE"
    printer_status: str | None = None
    card_reader_status: str | None = None
    overall_status: str | None = None
    last_seen_at: datetime | None = None


class ProcessorStatusOut(BaseModel):
    name: str = "mock_sandbox"
    mode: str = "SANDBOX"
    status: str = "ONLINE"
    message: str = "Sandbox mock processor — no live acquiring"
    recent_outcomes: dict[str, int] = Field(default_factory=dict)
    live_acquiring: bool = False
    configured: bool = True


class AdminDashboardOut(BaseModel):
    merchants: int = 0
    settlements: int = 0
    today_transactions: int = 0
    today_volume: float = 0.0
    total_volume: float = 0.0
    approved: int = 0
    declined: int = 0
    refunded: int = 0
    voided: int = 0
    pending: int = 0
    approval_rate: float = 0.0
    currency: str = "CAD"
    transactions_per_day: list[DayPoint] = Field(default_factory=list)
    volume_per_day: list[DayPoint] = Field(default_factory=list)
    protocol_usage: list[NamedCount] = Field(default_factory=list)
    devices: list[DeviceStatusRow] = Field(default_factory=list)
    device_summary: dict[str, int] = Field(default_factory=dict)
    processor: ProcessorStatusOut = Field(default_factory=ProcessorStatusOut)
    sources: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime


def _bucket(status: str) -> str | None:
    s = (status or "").strip()
    if s in _APPROVED or s.upper() in _APPROVED:
        return "approved"
    if s in _DECLINED or s.upper() in _DECLINED:
        return "declined"
    if s in _REFUNDED or s.upper() in _REFUNDED:
        return "refunded"
    if s in _VOIDED or s.upper() in _VOIDED:
        return "voided"
    if s in _PENDING or s.upper() in _PENDING:
        return "pending"
    upper = s.upper()
    if upper in {"FAILED", "TIMEOUT", "ERROR"}:
        return "declined"
    return None


def _day_key(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date().isoformat()


def _minor_to_major(amount_minor: int, currency: str = "CAD") -> float:
    # Most terminal currencies use 2 fraction digits in this sandbox.
    _ = currency
    return float(Decimal(amount_minor) / Decimal(100))


class AdminDashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.merchants = MerchantRepository(session)
        self.transactions = TransactionRepository(session)
        self.settlements = SettlementRepository(session)
        self.store = get_terminal_session_store()

    async def build(self, *, days: int = 14) -> AdminDashboardOut:
        now = datetime.now(timezone.utc)
        today = now.date()
        start = now - timedelta(days=max(days - 1, 0))

        merchants_count = await self.merchants.count()
        settlements_count = await self.settlements.count()

        counts = Counter()
        today_count = 0
        today_volume = 0.0
        total_volume = 0.0
        per_day_count: dict[str, int] = defaultdict(int)
        per_day_volume: dict[str, float] = defaultdict(float)
        protocols: Counter[str] = Counter()
        processor_outcomes: Counter[str] = Counter()
        sources = Counter()
        currency = "CAD"

        # --- Terminal sandbox sessions (in-memory) ---
        sessions = self.store.list_all(limit=1000)
        for rec in sessions:
            sources["terminal"] += 1
            bucket = _bucket(rec.state)
            if bucket:
                counts[bucket] += 1
            amount = _minor_to_major(rec.amount_minor, rec.currency)
            total_volume += amount
            currency = rec.currency or currency
            day = _day_key(rec.created_at)
            if rec.created_at.astimezone(timezone.utc) >= start:
                per_day_count[day] += 1
                per_day_volume[day] += amount
            if rec.created_at.astimezone(timezone.utc).date() == today:
                today_count += 1
                today_volume += amount
            proto = rec.protocol_code or rec.protocol_id or "unknown"
            protocols[proto] += 1
            if rec.processor_status:
                processor_outcomes[rec.processor_status] += 1
            elif bucket:
                processor_outcomes[bucket.upper()] += 1

        # --- Legacy DB payments ---
        rows = (
            await self.session.scalars(
                select(Transaction)
                .where(Transaction.deleted_at.is_(None))
                .order_by(Transaction.created_at.desc())
                .limit(2000)
            )
        ).all()
        for tx in rows:
            sources["legacy"] += 1
            bucket = _bucket(tx.status)
            if bucket:
                counts[bucket] += 1
            amount = float(tx.amount or 0)
            total_volume += amount
            currency = tx.currency or currency
            created = tx.payment_date or tx.created_at
            if created is None:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            day = _day_key(created)
            if created >= start:
                per_day_count[day] += 1
                per_day_volume[day] += amount
            if created.date() == today:
                today_count += 1
                today_volume += amount
            extra = tx.extra_data or {}
            proto = extra.get("protocol_code") or extra.get("protocol") or "legacy"
            protocols[str(proto)] += 1

        decided = counts["approved"] + counts["declined"]
        approval_rate = (
            round((counts["approved"] / decided) * 100.0, 1) if decided else 0.0
        )

        # Fill continuous day series
        series_count: list[DayPoint] = []
        series_volume: list[DayPoint] = []
        for i in range(days):
            d = (start + timedelta(days=i)).date().isoformat()
            series_count.append(DayPoint(date=d, count=per_day_count.get(d, 0)))
            series_volume.append(
                DayPoint(date=d, count=per_day_count.get(d, 0), volume=round(per_day_volume.get(d, 0.0), 2))
            )

        devices = await self._devices()
        device_summary = Counter(d.overall_status or d.connectivity_status for d in devices)

        from app.processors.factory import get_payment_processor

        try:
            active = get_payment_processor()
            desc = active.describe()
            proc_name = str(desc["name"])
            proc_mode = str(desc["environment"])
            live = bool(desc.get("live_acquiring"))
            configured = True
            base_msg = (
                "Sandbox mock processor — no live acquiring"
                if active.is_sandbox
                else f"Processor {proc_name} ({proc_mode})"
            )
        except Exception as exc:  # noqa: BLE001 — surface config errors in admin UI
            proc_name = "unconfigured"
            proc_mode = "SANDBOX"
            live = False
            configured = False
            base_msg = str(exc)

        processor = ProcessorStatusOut(
            name=proc_name,
            mode=proc_mode,
            recent_outcomes=dict(processor_outcomes.most_common(8)),
            status="ONLINE" if configured and (sessions or rows) else ("ERROR" if not configured else "IDLE"),
            message=(
                base_msg
                if sessions or rows or not configured
                else "No recent processor activity"
            ),
            live_acquiring=live,
            configured=configured,
        )

        return AdminDashboardOut(
            merchants=merchants_count,
            settlements=settlements_count,
            today_transactions=today_count,
            today_volume=round(today_volume, 2),
            total_volume=round(total_volume, 2),
            approved=counts["approved"],
            declined=counts["declined"],
            refunded=counts["refunded"],
            voided=counts["voided"],
            pending=counts["pending"],
            approval_rate=approval_rate,
            currency=currency,
            transactions_per_day=series_count,
            volume_per_day=series_volume,
            protocol_usage=[
                NamedCount(name=n, count=c) for n, c in protocols.most_common(16)
            ],
            devices=devices,
            device_summary=dict(device_summary),
            processor=processor,
            sources=dict(sources),
            generated_at=now,
        )

    async def _devices(self) -> list[DeviceStatusRow]:
        rows = (
            await self.session.scalars(
                select(SunmiDevice).order_by(SunmiDevice.last_seen_at.desc().nulls_last()).limit(50)
            )
        ).all()
        out: list[DeviceStatusRow] = []
        for d in rows:
            info = await self.session.scalar(
                select(DeviceInformation).where(DeviceInformation.external_id == d.serial_number)
            )
            extra: dict[str, Any] = info.extra_data or {} if info else {}
            overall = extra.get("overall_status") or extra.get("connectivity_status")
            if not overall:
                overall = "ONLINE" if d.status == "active" else "OFFLINE"
            out.append(
                DeviceStatusRow(
                    id=str(d.id),
                    serial_number=d.serial_number,
                    model=d.model,
                    manufacturer=info.manufacturer if info else None,
                    connectivity_status=extra.get("connectivity_status") or overall,
                    printer_status=extra.get("printer_status"),
                    card_reader_status=extra.get("card_reader_status"),
                    overall_status=overall,
                    last_seen_at=d.last_seen_at,
                )
            )
        return out
