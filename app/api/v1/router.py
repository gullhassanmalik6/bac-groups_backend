from fastapi import APIRouter

from app.api.v1.routes import (
    admin,
    audit_logs,
    auth,
    devices,
    health,
    merchants,
    payments,
    payouts,
    pos,
    terminal,
    website,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(merchants.router)
api_router.include_router(payments.router)
api_router.include_router(payouts.router)
api_router.include_router(pos.router)
api_router.include_router(terminal.router)
api_router.include_router(devices.router)
api_router.include_router(audit_logs.router)
api_router.include_router(website.router)
api_router.include_router(admin.router)
