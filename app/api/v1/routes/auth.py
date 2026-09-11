from fastapi import APIRouter, Request, status

from app.api.v1.deps import CurrentUser, DbSession, get_client_ip
from app.core.responses import success_response
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UserOut,
)
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, session: DbSession):
    service = AuthService(session)
    user = await service.register(payload)
    await AuditService(session).record(
        action="user_registered",
        resource_type="user",
        resource_id=str(user.id),
        actor_user_id=user.id,
        ip_address=await get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        details={"email": user.email, "role": user.role_code},
    )
    return success_response(
        data=user.model_dump(mode="json"),
        message="User registered",
        status_code=201,
    )


@router.post("/login")
async def login(payload: LoginRequest, request: Request, session: DbSession):
    service = AuthService(session)
    tokens, user = await service.login(
        payload,
        ip_address=await get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    await AuditService(session).record(
        action="user_login",
        resource_type="user",
        resource_id=str(user.id),
        actor_user_id=user.id,
        ip_address=await get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        details={"email": user.email, "role": user.role_code, "result": "success"},
    )
    body = AuthResponse(tokens=tokens, user=user)
    return success_response(data=body.model_dump(mode="json"), message="Login successful")


@router.post("/refresh")
async def refresh(payload: RefreshRequest, session: DbSession):
    service = AuthService(session)
    tokens = await service.refresh(payload.refresh_token)
    return success_response(data=tokens.model_dump(mode="json"), message="Token refreshed")


@router.post("/logout")
async def logout(payload: LogoutRequest, request: Request, session: DbSession):
    service = AuthService(session)
    await service.logout(payload.refresh_token)
    await AuditService(session).record(
        action="user_logout",
        resource_type="user",
        ip_address=await get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        details={"result": "success"},
    )
    return success_response(message="Logged out")


@router.get("/me")
async def me(user: CurrentUser):
    return success_response(data=UserOut.model_validate(user).model_dump(mode="json"))
