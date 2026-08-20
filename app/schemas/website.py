from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.auth import APIModel


class ServiceOut(APIModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    slug: str
    title: str
    summary: str
    description: str
    icon: str
    features: list
    image_url: str = Field(serialization_alias="imageUrl")


class ProjectOut(APIModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    slug: str
    title: str
    category: str
    summary: str
    description: str
    location: str
    year: str
    image_url: str = Field(serialization_alias="imageUrl")
    tags: list


class FaqOut(APIModel):
    id: UUID
    question: str
    answer: str
    category: str


class TestimonialOut(APIModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    name: str
    role: str
    company: str
    quote: str
    rating: int
    avatar_url: str | None = Field(default=None, serialization_alias="avatarUrl")


class ContactCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    full_name: str = Field(min_length=2, max_length=255, alias="fullName")
    email: EmailStr
    phone: str = Field(min_length=8, max_length=32)
    company: str = Field(min_length=2, max_length=255)
    subject: str = Field(min_length=3, max_length=255)
    message: str = Field(min_length=20)


class ContactOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticket_id: str = Field(serialization_alias="ticketId")


class NewsletterCreate(BaseModel):
    email: EmailStr


class NewsletterOut(BaseModel):
    subscribed: bool
