"""Request/response schemas for /v1/events."""

from datetime import datetime

from pydantic import BaseModel, Field


class EventCreateIn(BaseModel):
    """Payload for POST /v1/events."""

    event_type: str = Field(..., min_length=1, max_length=120)
    data: dict = Field(default_factory=dict)


class EventOut(BaseModel):
    """Response schema for Event."""

    id: int
    org_id: int
    event_type: str
    payload: dict
    created_at: datetime

    model_config = {"from_attributes": True}
