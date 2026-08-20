from fastapi import APIRouter

from app.api.v1.deps import CurrentUser, DbSession, require_roles
from app.core.enums import UserRole
from app.core.responses import success_response
from app.models.user import User
from app.repositories.merchant import MerchantRepository
from app.repositories.transaction import SettlementRepository, TransactionRepository
from fastapi import Depends

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
async def dashboard(
    session: DbSession,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
):
    merchants = MerchantRepository(session)
    transactions = TransactionRepository(session)
    settlements = SettlementRepository(session)
    return success_response(
        data={
            "merchants": await merchants.count(),
            "transactions": await transactions.count(),
            "settlements": await settlements.count(),
        }
    )


@router.get("/me-check")
async def admin_me(user: CurrentUser):
    return success_response(
        data={"id": str(user.id), "role": user.role_code, "email": user.email}
    )
