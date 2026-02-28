"""
Service layer for usage metering.

Provides functions to record usage events and count them for quota checks.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.usage_event import UsageEvent

UsageGroupBy = Literal["hour", "day", "month"]


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


def aggregate_usage(
    db: Session,
    *,
    org_id: int,
    from_date: date,
    to_date: date,
    group_by: UsageGroupBy,
) -> tuple[int, list[dict[str, int | str]]]:
    """
    Aggregate usage rows for an org in an inclusive date range.

    Returns (total_requests, series) where series is sorted ascending by period.
    """
    range_start = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
    range_end_exclusive = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=timezone.utc)

    stmt = (
        select(UsageEvent.created_at, UsageEvent.response_time_ms)
        .where(
            UsageEvent.org_id == org_id,
            UsageEvent.created_at >= range_start,
            UsageEvent.created_at < range_end_exclusive,
        )
        .order_by(UsageEvent.created_at.asc())
    )

    rows = db.execute(stmt).all()
    buckets: dict[datetime, dict[str, int]] = defaultdict(lambda: {"count": 0, "latency_sum": 0})

    for created_at, response_time_ms in rows:
        bucket_start = _bucket_start_utc(created_at, group_by)
        buckets[bucket_start]["count"] += 1
        buckets[bucket_start]["latency_sum"] += int(response_time_ms)

    series: list[dict[str, int | str]] = []
    for bucket_start in sorted(buckets):
        count = buckets[bucket_start]["count"]
        latency_sum = buckets[bucket_start]["latency_sum"]
        series.append(
            {
                "period": _format_period(bucket_start, group_by),
                "count": count,
                "avg_latency_ms": int(round(latency_sum / count)) if count else 0,
            }
        )

    return len(rows), series


def _bucket_start_utc(value: datetime, group_by: UsageGroupBy) -> datetime:
    utc_value = _as_utc(value)
    if group_by == "hour":
        return utc_value.replace(minute=0, second=0, microsecond=0)
    if group_by == "day":
        return utc_value.replace(hour=0, minute=0, second=0, microsecond=0)
    return utc_value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _format_period(bucket_start: datetime, group_by: UsageGroupBy) -> str:
    if group_by == "hour":
        return bucket_start.strftime("%Y-%m-%dT%H:00:00Z")
    if group_by == "day":
        return bucket_start.date().isoformat()
    return bucket_start.strftime("%Y-%m")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
