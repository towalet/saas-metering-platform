from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Rate limit: max requests per minute for API-key-authed endpoints to prevent abuse. Configurable per-org via the `rate_limit_rpm` column (rpm - means requests per minute).
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=60, server_default="60", nullable=False)

    # Quota: max requests per calendar month to track for billing purposes
    monthly_quota: Mapped[int] = mapped_column(Integer, default=10000, server_default="10000", nullable=False)

    # members: relationship to OrgMember (users in this org)
    members = relationship("OrgMember", back_populates="org", cascade="all, delete-orphan")

    # api_keys: relationship to ApiKey (API keys belonging to this org)
    api_keys = relationship("ApiKey", back_populates="org", cascade="all, delete-orphan")
