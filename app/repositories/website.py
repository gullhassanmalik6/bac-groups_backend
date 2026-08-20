from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.website import (
    ContactMessage,
    Faq,
    NewsletterSubscriber,
    Testimonial,
    WebsiteProject,
    WebsiteService,
)
from app.repositories.base import BaseRepository


class WebsiteServiceRepository(BaseRepository[WebsiteService]):
    model = WebsiteService

    async def list_published(self) -> list[WebsiteService]:
        result = await self.session.execute(
            self._base_query()
            .where(WebsiteService.is_published.is_(True))
            .order_by(WebsiteService.sort_order.asc())
        )
        return list(result.scalars().all())


class WebsiteProjectRepository(BaseRepository[WebsiteProject]):
    model = WebsiteProject

    async def list_published(self, category: str | None = None) -> list[WebsiteProject]:
        query = self._base_query().where(WebsiteProject.is_published.is_(True))
        if category and category != "All":
            query = query.where(WebsiteProject.category == category)
        result = await self.session.execute(query.order_by(WebsiteProject.created_at.desc()))
        return list(result.scalars().all())


class FaqRepository(BaseRepository[Faq]):
    model = Faq

    async def list_published(self) -> list[Faq]:
        result = await self.session.execute(
            self._base_query()
            .where(Faq.is_published.is_(True))
            .order_by(Faq.sort_order.asc())
        )
        return list(result.scalars().all())


class TestimonialRepository(BaseRepository[Testimonial]):
    model = Testimonial

    async def list_published(self) -> list[Testimonial]:
        result = await self.session.execute(
            self._base_query().where(Testimonial.is_published.is_(True))
        )
        return list(result.scalars().all())


class ContactMessageRepository(BaseRepository[ContactMessage]):
    model = ContactMessage


class NewsletterRepository(BaseRepository[NewsletterSubscriber]):
    model = NewsletterSubscriber

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_email(self, email: str) -> NewsletterSubscriber | None:
        result = await self.session.execute(
            select(NewsletterSubscriber).where(
                NewsletterSubscriber.email == email.lower(),
                NewsletterSubscriber.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def subscribe(self, email: str) -> NewsletterSubscriber:
        existing = await self.get_by_email(email)
        if existing:
            existing.is_active = True
            await self.session.flush()
            return existing
        subscriber = NewsletterSubscriber(
            email=email.lower(),
            is_active=True,
            subscribed_at=datetime.now(UTC),
        )
        return await self.add(subscriber)
