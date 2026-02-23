"""
UsageEvent model.

Records every API-key-authenticated request for metering and billing.
Denormalises org_id from the API key for fast org-level aggregation.
Composite index on (org_id, created_at) powers time-range queries.
"""

from sqlalchemy import ForeignKey, Integer, String, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_org_created", "org_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    api_key_id: Mapped[int] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True
    )
    org_id: Mapped[int] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )

    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
