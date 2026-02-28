"""Response schemas for usage reporting endpoints."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class UsagePeriodOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_date: date = Field(alias="from")
    to: date


class UsageSeriesPointOut(BaseModel):
    period: str
    count: int
    avg_latency_ms: int


class UsageReportOut(BaseModel):
    org_id: int
    period: UsagePeriodOut
    total_requests: int
    quota_limit: int
    quota_used_pct: float
    series: list[UsageSeriesPointOut]
