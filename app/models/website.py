from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from app.database.types import JSONType, UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import TicketPriority, TicketStatus
from app.database.base import BaseModel


class WebsiteService(BaseModel):
    __tablename__ = "services"

    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(64), default="Smartphone")
    features: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WebsiteProject(BaseModel):
    __tablename__ = "projects"

    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    year: Mapped[str] = mapped_column(String(8), nullable=False)
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    tags: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProjectImage(BaseModel):
    __tablename__ = "project_images"

    project_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    alt_text: Mapped[Optional[str]] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Testimonial(BaseModel):
    __tablename__ = "testimonials"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(128), nullable=False)
    company: Mapped[str] = mapped_column(String(128), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Faq(BaseModel):
    __tablename__ = "faq"

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="General", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ContactMessage(BaseModel):
    __tablename__ = "contact_messages"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)


class NewsletterSubscriber(BaseModel):
    __tablename__ = "newsletter"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    subscribed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WebsiteSetting(BaseModel):
    __tablename__ = "website_settings"

    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)


class Notification(BaseModel):
    __tablename__ = "notifications"

    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE")
    )
    merchant_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("merchant_profiles.id", ondelete="CASCADE")
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)


class SupportTicket(BaseModel):
    __tablename__ = "support_tickets"

    merchant_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("merchant_profiles.id", ondelete="SET NULL")
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="SET NULL")
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=TicketStatus.OPEN, nullable=False)
    priority: Mapped[str] = mapped_column(
        String(32), default=TicketPriority.MEDIUM, nullable=False
    )


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(64))
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)


class SystemLog(BaseModel):
    __tablename__ = "system_logs"

    level: Mapped[str] = mapped_column(String(16), nullable=False)
    logger_name: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)


class Webhook(BaseModel):
    __tablename__ = "webhooks"

    merchant_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("merchant_profiles.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_url: Mapped[str] = mapped_column(String(512), nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Country(BaseModel):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Currency(BaseModel):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Language(BaseModel):
    __tablename__ = "languages"

    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PrinterLog(BaseModel):
    __tablename__ = "printer_logs"

    device_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("sunmi_devices.id", ondelete="SET NULL")
    )
    transaction_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("transactions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)
