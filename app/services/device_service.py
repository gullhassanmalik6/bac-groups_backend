"""Device registration and heartbeat for POS terminals."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import AppException, NotFoundError
from app.models.merchant import DeviceInformation, SunmiDevice
from app.repositories.merchant import MerchantRepository
from app.services.audit_service import AuditService


class RegisterDeviceRequest(BaseModel):
    serial_number: str = Field(min_length=3, max_length=128)
    model: str = Field(default="Sunmi V3", max_length=64)
    android_version: str | None = Field(default=None, max_length=32)
    manufacturer: str = Field(default="Sunmi", max_length=64)
    app_version: str | None = Field(default=None, max_length=32)
    connectivity_status: str | None = Field(default=None, max_length=32)
    printer_status: str | None = Field(default=None, max_length=32)
    card_reader_status: str | None = Field(default=None, max_length=32)
    overall_status: str | None = Field(default=None, max_length=32)
    firmware: str | None = Field(default=None, max_length=128)


class DeviceHeartbeatRequest(BaseModel):
    device_id: UUID | None = None
    serial_number: str | None = Field(default=None, max_length=128)
    connectivity_status: str = Field(default="ONLINE", max_length=32)
    printer_status: str | None = Field(default=None, max_length=32)
    card_reader_status: str | None = Field(default=None, max_length=32)
    overall_status: str | None = Field(default=None, max_length=32)


class DeviceOut(BaseModel):
    id: UUID
    serial_number: str
    model: str
    android_version: str | None = None
    status: str
    last_seen_at: datetime | None = None
    merchant_id: UUID
    connectivity_status: str = "ONLINE"
    manufacturer: str | None = None
    app_version: str | None = None
    printer_status: str | None = None
    card_reader_status: str | None = None
    overall_status: str | None = None

    model_config = {"from_attributes": True}


def _extra_status(
    connectivity: str | None,
    printer: str | None,
    card_reader: str | None,
    overall: str | None,
) -> dict:
    return {
        k: v
        for k, v in {
            "connectivity_status": connectivity,
            "printer_status": printer,
            "card_reader_status": card_reader,
            "overall_status": overall,
        }.items()
        if v
    }


class DeviceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.merchants = MerchantRepository(session)
        self.audit = AuditService(session)

    async def register(self, user_id: UUID, payload: RegisterDeviceRequest) -> DeviceOut:
        merchant = await self.merchants.get_by_owner(user_id)
        if merchant is None:
            raise AppException("Merchant profile required", status_code=403)

        existing = await self.session.scalar(
            select(SunmiDevice).where(SunmiDevice.serial_number == payload.serial_number)
        )
        now = datetime.now(timezone.utc)
        if existing:
            if existing.merchant_id != merchant.id:
                raise AppException("Device serial already registered to another merchant", status_code=409)
            existing.model = payload.model
            existing.android_version = payload.android_version
            existing.last_seen_at = now
            existing.status = "active"
            await self.session.flush()
            device = existing
        else:
            device = SunmiDevice(
                merchant_id=merchant.id,
                serial_number=payload.serial_number,
                model=payload.model,
                android_version=payload.android_version,
                status="active",
                last_seen_at=now,
            )
            self.session.add(device)
            await self.session.flush()

        await self._upsert_info(
            merchant_id=merchant.id,
            sunmi_device_id=device.id,
            serial=payload.serial_number,
            manufacturer=payload.manufacturer,
            model=payload.model,
            android_version=payload.android_version,
            app_version=payload.app_version,
            extra=_extra_status(
                payload.connectivity_status,
                payload.printer_status,
                payload.card_reader_status,
                payload.overall_status,
            ),
            now=now,
        )

        await self.audit.record(
            action="device_registered",
            resource_type="device",
            resource_id=str(device.id),
            actor_user_id=user_id,
            details={"serial_number": device.serial_number, "model": device.model},
        )
        return await self._to_out(device)

    async def heartbeat(self, user_id: UUID, payload: DeviceHeartbeatRequest) -> DeviceOut:
        merchant = await self.merchants.get_by_owner(user_id)
        if merchant is None:
            raise AppException("Merchant profile required", status_code=403)

        device: SunmiDevice | None = None
        if payload.device_id is not None:
            device = await self.session.get(SunmiDevice, payload.device_id)
        elif payload.serial_number:
            device = await self.session.scalar(
                select(SunmiDevice).where(SunmiDevice.serial_number == payload.serial_number)
            )
        if device is None or device.merchant_id != merchant.id:
            raise NotFoundError("Device not found — register first")

        now = datetime.now(timezone.utc)
        device.last_seen_at = now
        device.status = "active"
        await self.session.flush()

        info = await self.session.scalar(
            select(DeviceInformation).where(DeviceInformation.external_id == device.serial_number)
        )
        extra = dict(info.extra_data or {}) if info else {}
        extra.update(
            _extra_status(
                payload.connectivity_status,
                payload.printer_status,
                payload.card_reader_status,
                payload.overall_status,
            )
        )
        await self._upsert_info(
            merchant_id=merchant.id,
            sunmi_device_id=device.id,
            serial=device.serial_number,
            manufacturer=info.manufacturer if info else "Generic",
            model=device.model,
            android_version=device.android_version,
            app_version=info.app_version if info else None,
            extra=extra,
            now=now,
        )
        await self.audit.record(
            action="device_heartbeat",
            resource_type="device",
            resource_id=str(device.id),
            actor_user_id=user_id,
            details={"overall_status": payload.overall_status},
        )
        return await self._to_out(device)

    async def list_devices(self, user_id: UUID) -> list[DeviceOut]:
        merchant = await self.merchants.get_by_owner(user_id)
        if merchant is None:
            raise AppException("Merchant profile required", status_code=403)
        rows = (
            await self.session.scalars(
                select(SunmiDevice)
                .where(SunmiDevice.merchant_id == merchant.id)
                .order_by(SunmiDevice.created_at.desc())
            )
        ).all()
        return [await self._to_out(d) for d in rows]

    async def get_device(self, user_id: UUID, device_id: UUID) -> DeviceOut:
        merchant = await self.merchants.get_by_owner(user_id)
        if merchant is None:
            raise AppException("Merchant profile required", status_code=403)
        device = await self.session.get(SunmiDevice, device_id)
        if device is None or device.merchant_id != merchant.id:
            raise NotFoundError("Device not found")
        return await self._to_out(device)

    async def _upsert_info(
        self,
        *,
        merchant_id: UUID,
        sunmi_device_id: UUID,
        serial: str,
        manufacturer: str,
        model: str,
        android_version: str | None,
        app_version: str | None,
        extra: dict,
        now: datetime,
    ) -> None:
        info = await self.session.scalar(
            select(DeviceInformation).where(DeviceInformation.external_id == serial)
        )
        if info:
            info.sunmi_device_id = sunmi_device_id
            info.manufacturer = manufacturer
            info.model_name = model
            info.os_version = android_version
            info.app_version = app_version
            info.last_seen_at = now
            info.status = "active"
            merged = dict(info.extra_data or {})
            merged.update(extra)
            info.extra_data = merged
        else:
            self.session.add(
                DeviceInformation(
                    merchant_id=merchant_id,
                    sunmi_device_id=sunmi_device_id,
                    external_id=serial,
                    manufacturer=manufacturer,
                    model_name=model,
                    os_name="Android",
                    os_version=android_version,
                    app_version=app_version,
                    last_seen_at=now,
                    status="active",
                    extra_data=extra or None,
                )
            )
        await self.session.flush()

    async def _to_out(self, device: SunmiDevice) -> DeviceOut:
        info = await self.session.scalar(
            select(DeviceInformation).where(DeviceInformation.external_id == device.serial_number)
        )
        extra = info.extra_data or {} if info else {}
        connectivity = extra.get("connectivity_status") or (
            "ONLINE" if device.status == "active" else "OFFLINE"
        )
        return DeviceOut(
            id=device.id,
            serial_number=device.serial_number,
            model=device.model,
            android_version=device.android_version,
            status=device.status,
            last_seen_at=device.last_seen_at,
            merchant_id=device.merchant_id,
            connectivity_status=connectivity,
            manufacturer=info.manufacturer if info else None,
            app_version=info.app_version if info else None,
            printer_status=extra.get("printer_status"),
            card_reader_status=extra.get("card_reader_status"),
            overall_status=extra.get("overall_status"),
        )
