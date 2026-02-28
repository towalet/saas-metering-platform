"""Usage reporting endpoints for org dashboards."""

from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.roles import require_org_role
from app.db.deps import get_db
from app.models.orgs import Org
from app.models.user import User
from app.schemas.usage import UsagePeriodOut, UsageReportOut
from app.services.usage import aggregate_usage

router = APIRouter(prefix="/orgs/{org_id}/usage", tags=["usage"])


@router.get("", response_model=UsageReportOut)
def usage_report_endpoint(
    org_id: int,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    group_by: Literal["hour", "day", "month"] = Query(default="day"),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    require_org_role(db, org_id, me.id, allowed={"owner", "admin"})

    today = datetime.now(timezone.utc).date()
    resolved_from = from_date or today.replace(day=1)
    resolved_to = to_date or today

    if resolved_from > resolved_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be on or before to_date",
        )

    total_requests, series = aggregate_usage(
        db,
        org_id=org_id,
        from_date=resolved_from,
        to_date=resolved_to,
        group_by=group_by,
    )

    quota_limit = db.execute(select(Org.monthly_quota).where(Org.id == org_id)).scalar_one_or_none() or 0
    quota_used_pct = round((total_requests / quota_limit) * 100, 1) if quota_limit > 0 else 0.0

    return UsageReportOut(
        org_id=org_id,
        period=UsagePeriodOut(from_date=resolved_from, to=resolved_to),
        total_requests=total_requests,
        quota_limit=quota_limit,
        quota_used_pct=quota_used_pct,
        series=series,
    )
