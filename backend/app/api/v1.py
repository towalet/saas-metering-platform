"""
Protected API v1 routes.

External consumers call these endpoints with X-API-Key.
Full pipeline: API key auth -> rate limit -> quota -> process -> record usage.
"""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis_dep
from app.core.security import get_current_api_key
from app.db.deps import get_db
from app.models.api_key import ApiKey
from app.models.orgs import Org
from app.schemas.events import EventCreateIn, EventOut
from app.services.events import create_event, list_events_for_org
from app.services.usage import record_usage

router = APIRouter(prefix="/v1", tags=["v1"])


def _get_api_key_with_rate_limit(
    response: Response,
    api_key: ApiKey = Depends(get_current_api_key),
    db: Session = Depends(get_db),
    redis_client: Any = Depends(get_redis_dep),
) -> ApiKey:
    """
    Authenticate via API key (includes quota check) and enforce rate limit.
    Sets X-RateLimit-* headers on the response.
    """
    org = db.execute(select(Org).where(Org.id == api_key.org_id)).scalar_one_or_none()
    limit = org.rate_limit_rpm if org else 60

    result = check_rate_limit(redis_client, key_id=api_key.id, limit=limit)

    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(result.reset_at)},
        )

    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = str(result.reset_at)

    return api_key


@router.post("/events", response_model=EventOut, status_code=201)
def post_event(
    request: Request,
    payload: EventCreateIn,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(_get_api_key_with_rate_limit),
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
    api_key: ApiKey = Depends(_get_api_key_with_rate_limit),
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
