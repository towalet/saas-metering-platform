"""Service layer for Event CRUD."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event


def create_event(
    db: Session,
    *,
    org_id: int,
    api_key_id: int,
    event_type: str,
    payload: dict,
) -> Event:
    """Insert a new event."""
    event = Event(
        org_id=org_id,
        api_key_id=api_key_id,
        event_type=event_type,
        payload=payload,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events_for_org(
    db: Session,
    org_id: int,
    *,
    limit: int = 100,
) -> list[Event]:
    """List recent events for an org, newest first."""
    stmt = (
        select(Event)
        .where(Event.org_id == org_id)
        .order_by(Event.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())
