from fastapi import APIRouter, Query, status

from app.api.v1.deps import DbSession
from app.core.responses import success_response
from app.schemas.website import ContactCreate, NewsletterCreate
from app.services.website_service import WebsiteService

router = APIRouter(prefix="/website", tags=["Website"])


@router.get("/services")
async def list_services(session: DbSession):
    service = WebsiteService(session)
    items = await service.list_services()
    return success_response(data=[item.model_dump(mode="json", by_alias=True) for item in items])


@router.get("/projects")
async def list_projects(session: DbSession, category: str | None = Query(default=None)):
    service = WebsiteService(session)
    items = await service.list_projects(category=category)
    return success_response(data=[item.model_dump(mode="json", by_alias=True) for item in items])


@router.get("/faq")
async def list_faqs(session: DbSession):
    service = WebsiteService(session)
    items = await service.list_faqs()
    return success_response(data=[item.model_dump(mode="json", by_alias=True) for item in items])


@router.get("/testimonials")
async def list_testimonials(session: DbSession):
    service = WebsiteService(session)
    items = await service.list_testimonials()
    return success_response(data=[item.model_dump(mode="json", by_alias=True) for item in items])


@router.post("/contact", status_code=status.HTTP_201_CREATED)
async def submit_contact(payload: ContactCreate, session: DbSession):
    service = WebsiteService(session)
    result = await service.submit_contact(payload)
    return success_response(
        data=result.model_dump(mode="json", by_alias=True),
        message="Contact message received",
        status_code=201,
    )


@router.post("/newsletter", status_code=status.HTTP_201_CREATED)
async def subscribe_newsletter(payload: NewsletterCreate, session: DbSession):
    service = WebsiteService(session)
    result = await service.subscribe(payload)
    return success_response(
        data=result.model_dump(mode="json"),
        message="Subscribed",
        status_code=201,
    )
