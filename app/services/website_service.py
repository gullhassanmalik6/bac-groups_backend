from sqlalchemy.ext.asyncio import AsyncSession

from app.models.website import ContactMessage
from app.repositories.website import (
    ContactMessageRepository,
    FaqRepository,
    NewsletterRepository,
    TestimonialRepository,
    WebsiteProjectRepository,
    WebsiteServiceRepository,
)
from app.schemas.website import (
    ContactCreate,
    ContactOut,
    FaqOut,
    NewsletterCreate,
    NewsletterOut,
    ProjectOut,
    ServiceOut,
    TestimonialOut,
)


class WebsiteService:
    def __init__(self, session: AsyncSession) -> None:
        self.services = WebsiteServiceRepository(session)
        self.projects = WebsiteProjectRepository(session)
        self.faqs = FaqRepository(session)
        self.testimonials = TestimonialRepository(session)
        self.contacts = ContactMessageRepository(session)
        self.newsletter = NewsletterRepository(session)

    async def list_services(self) -> list[ServiceOut]:
        items = await self.services.list_published()
        return [
            ServiceOut(
                id=item.id,
                slug=item.slug,
                title=item.title,
                summary=item.summary,
                description=item.description,
                icon=item.icon,
                features=item.features or [],
                image_url=item.image_url,
            )
            for item in items
        ]

    async def list_projects(self, category: str | None = None) -> list[ProjectOut]:
        items = await self.projects.list_published(category=category)
        return [
            ProjectOut(
                id=item.id,
                slug=item.slug,
                title=item.title,
                category=item.category,
                summary=item.summary,
                description=item.description,
                location=item.location,
                year=item.year,
                image_url=item.image_url,
                tags=item.tags or [],
            )
            for item in items
        ]

    async def list_faqs(self) -> list[FaqOut]:
        items = await self.faqs.list_published()
        return [FaqOut.model_validate(item) for item in items]

    async def list_testimonials(self) -> list[TestimonialOut]:
        items = await self.testimonials.list_published()
        return [TestimonialOut.model_validate(item) for item in items]

    async def submit_contact(self, payload: ContactCreate) -> ContactOut:
        message = ContactMessage(
            full_name=payload.full_name,
            email=payload.email.lower(),
            phone=payload.phone,
            company=payload.company,
            subject=payload.subject,
            message=payload.message,
        )
        message = await self.contacts.add(message)
        return ContactOut(ticket_id=str(message.id))

    async def subscribe(self, payload: NewsletterCreate) -> NewsletterOut:
        await self.newsletter.subscribe(payload.email)
        return NewsletterOut(subscribed=True)
