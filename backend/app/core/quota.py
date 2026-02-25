from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orgs import Org
from app.services.usage import count_usage_current_month

# Custom exception for when the monthly quota is exceeded.
@dataclass
class MonthlyQuotaExceededError(Exception):
    limit: int
    used: int
    resets_at: str

# Get the datetime of the first day of the next month in UTC.
def _next_month_start_utc(now: datetime) -> datetime:
    if now.month == 12:
        # If the current month is December, set the reset date to January of the next year.
        return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    # If the current month is not December, set the reset date to the first day of the next month.
    return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

# Convert a datetime to a ISO 8601 string in UTC with no microseconds and no timezone offset.
def _iso_utc_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

# Enforce the monthly quota for an org. If the quota is exceeded, raise a MonthlyQuotaExceededError.
def enforce_monthly_quota(db: Session, org_id: int) -> None:
    # Get the monthly quota for the org.
    quota = db.execute(select(Org.monthly_quota).where(Org.id == org_id)).scalar_one_or_none()
    if quota is None:
        return

    # Get the number of usage events for the org in the current month.
    used = count_usage_current_month(db, org_id)
    # If the usage is greater than or equal to the quota, raise a MonthlyQuotaExceededError.
    if used >= quota:
        raise MonthlyQuotaExceededError(
            limit=quota,
            used=used,
            resets_at=_iso_utc_z(_next_month_start_utc(datetime.now(timezone.utc))),
        )