"""
Protected API v1 routes.

External consumers call these endpoints with X-API-Key.
Full pipeline: API key auth -> rate limit -> quota -> process -> record usage.
Rate limiting and X-RateLimit-* headers are now handled by get_current_api_key.
"""

import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.security import get_current_api_key
from app.db.deps import get_db
from app.models.api_key import ApiKey
from app.schemas.events import EventCreateIn, EventOut
from app.services.events import create_event, list_events_for_org
from app.services.usage import record_usage

router = APIRouter(prefix="/v1", tags=["v1"])


@router.post("/events", response_model=EventOut, status_code=201)
def post_event(
    request: Request,
    payload: EventCreateIn,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    """Ingest a custom event. Accepts event_type and arbitrary data payload."""
    start = time.perf_counter()
    try:
        event = create_event(
            db,
            org_id=api_key.org_id,
            api_key_id=api_key.id,
            event_type=payload.event_type,
            payload=payload.data or {},
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        record_usage(
            db,
            api_key_id=api_key.id,
            org_id=api_key.org_id,
            method=request.method,
            path=request.url.path,
            status_code=201,
            response_time_ms=elapsed_ms,
        )
        return event
    except Exception:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        record_usage(
            db,
            api_key_id=api_key.id,
            org_id=api_key.org_id,
            method=request.method,
            path=request.url.path,
            status_code=500,
            response_time_ms=elapsed_ms,
        )
        raise


@router.get("/events", response_model=list[EventOut])
def get_events(
    request: Request,
    limit: int = 100,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    """List recent events for the org tied to the API key."""
    start = time.perf_counter()
    try:
        events = list_events_for_org(db, org_id=api_key.org_id, limit=limit)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        record_usage(
            db,
            api_key_id=api_key.id,
            org_id=api_key.org_id,
            method=request.method,
            path=request.url.path,
            status_code=200,
            response_time_ms=elapsed_ms,
        )
        return events
    except Exception:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        record_usage(
            db,
            api_key_id=api_key.id,
            org_id=api_key.org_id,
            method=request.method,
            path=request.url.path,
            status_code=500,
            response_time_ms=elapsed_ms,
        )
        raise
