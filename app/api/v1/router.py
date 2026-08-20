from fastapi import APIRouter

from app.api.v1.routes import admin, auth, health, merchants, payments, website

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(merchants.router)
api_router.include_router(payments.router)
api_router.include_router(website.router)
api_router.include_router(admin.router)
