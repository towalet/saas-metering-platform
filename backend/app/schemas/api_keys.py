"""
Pydantic schemas for API key endpoints.

Three distinct response shapes:
- ApiKeyCreateOut: returned ONCE at creation -- includes the full plaintext key.
- ApiKeyOut:       returned on list/get  -- only shows the prefix, never the secret.
- ApiKeyCreateIn:  the request body for creating a key.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreateIn(BaseModel):
    """What the user sends to create a new key."""
    name: str = Field(min_length=1, max_length=120, examples=["Production Backend"])


class ApiKeyCreateOut(BaseModel):
    """Returned ONCE at creation time -- the only time the full key is visible."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key: str  # the full plaintext key, shown only here
    key_prefix: str
    created_at: datetime


class ApiKeyOut(BaseModel):
    """Returned on list/get, the secret is never included."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None

