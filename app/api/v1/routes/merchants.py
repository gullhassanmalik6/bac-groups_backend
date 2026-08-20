from fastapi import APIRouter, status

from app.api.v1.deps import CurrentUser, DbSession
from app.core.responses import success_response
from app.schemas.merchant import MerchantCreate, WalletCreate
from app.services.payment_service import MerchantService

router = APIRouter(prefix="/merchants", tags=["Merchants"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_merchant(payload: MerchantCreate, session: DbSession, user: CurrentUser):
    service = MerchantService(session)
    merchant = await service.create_merchant(user.id, payload)
    return success_response(
        data=merchant.model_dump(mode="json"),
        message="Merchant created",
        status_code=201,
    )


@router.get("/me")
async def get_my_merchant(session: DbSession, user: CurrentUser):
    service = MerchantService(session)
    merchant = await service.get_my_merchant(user.id)
    return success_response(data=merchant.model_dump(mode="json"))


@router.post("/me/wallets", status_code=status.HTTP_201_CREATED)
async def add_wallet(payload: WalletCreate, session: DbSession, user: CurrentUser):
    service = MerchantService(session)
    wallet = await service.add_wallet(user.id, payload)
    return success_response(
        data=wallet.model_dump(mode="json"),
        message="Wallet added",
        status_code=201,
    )


@router.get("/me/wallets")
async def list_wallets(session: DbSession, user: CurrentUser):
    service = MerchantService(session)
    wallets = await service.list_wallets(user.id)
    return success_response(data=[item.model_dump(mode="json") for item in wallets])
