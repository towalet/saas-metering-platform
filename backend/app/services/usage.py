"""
Service layer for usage metering.

Provides functions to record usage events and count them for quota checks.
"""

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.usage_event import UsageEvent


def record_usage(
    db: Session,
    *,
    api_key_id: int,
    org_id: int,
    method: str,
    path: str,
    status_code: int,
    response_time_ms: int,
) -> UsageEvent:
    """Insert a single usage event row."""
    event = UsageEvent(
        api_key_id=api_key_id,
        org_id=org_id,
        method=method,
        path=path,
        status_code=status_code,
        response_time_ms=response_time_ms,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def count_usage_current_month(db: Session, org_id: int) -> int:
    """Count usage events for an org in the current calendar month (UTC)."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    stmt = (
        select(func.count())
        .select_from(UsageEvent)
        .where(
            UsageEvent.org_id == org_id,
            UsageEvent.created_at >= month_start,
        )
    )
    return db.execute(stmt).scalar_one()
