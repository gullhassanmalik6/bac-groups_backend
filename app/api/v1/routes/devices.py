from uuid import UUID

from fastapi import APIRouter, status

from app.api.v1.deps import CurrentUser, DbSession
from app.core.responses import success_response
from app.services.device_service import DeviceHeartbeatRequest, DeviceService, RegisterDeviceRequest

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_device(payload: RegisterDeviceRequest, session: DbSession, user: CurrentUser):
    service = DeviceService(session)
    out = await service.register(user.id, payload)
    return success_response(data=out.model_dump(mode="json"), message="Device registered", status_code=201)


@router.post("/heartbeat")
async def device_heartbeat(payload: DeviceHeartbeatRequest, session: DbSession, user: CurrentUser):
    service = DeviceService(session)
    out = await service.heartbeat(user.id, payload)
    return success_response(data=out.model_dump(mode="json"), message="Heartbeat recorded")


@router.get("")
async def list_devices(session: DbSession, user: CurrentUser):
    service = DeviceService(session)
    items = await service.list_devices(user.id)
    return success_response(data={"items": [i.model_dump(mode="json") for i in items], "total": len(items)})


@router.get("/{device_id}")
async def get_device(device_id: UUID, session: DbSession, user: CurrentUser):
    service = DeviceService(session)
    out = await service.get_device(user.id, device_id)
    return success_response(data=out.model_dump(mode="json"))
