"""
API key management endpoints.

All endpoints require JWT auth (the org dashboard user) and owner/admin role.
These are NOT the endpoints that external consumers call with API keys --
those will come in Phase 6 (/v1/events).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.api_keys import ApiKeyCreateIn, ApiKeyCreateOut, ApiKeyOut
from app.services.api_keys import create_api_key, list_api_keys, revoke_api_key
from app.core.roles import require_org_role

router = APIRouter(prefix="/orgs/{org_id}/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreateOut, status_code=201)
def create_key_endpoint(
    org_id: int,
    payload: ApiKeyCreateIn,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Generate a new API key for this org.

    The full plaintext key is returned in the response body.
    This is the ONLY time it will be visible, store it securely.
    """
    require_org_role(db, org_id, me.id, allowed={"owner", "admin"})
    api_key, plaintext = create_api_key(db, org_id, payload.name)

    # Build response, include the plaintext key this one time
    return ApiKeyCreateOut(
        id=api_key.id,
        name=api_key.name,
        key=plaintext,
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyOut])
def list_keys_endpoint(
    org_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """List all API keys for this org. The secret is never returned."""
    require_org_role(db, org_id, me.id, allowed={"owner", "admin"})
    return list_api_keys(db, org_id)


@router.delete("/{key_id}", response_model=ApiKeyOut)
def revoke_key_endpoint(
    org_id: int,
    key_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    Revoke (soft-delete) an API key.

    Revoked keys immediately stop authenticating requests.
    The key row is kept for audit history.
    """
    require_org_role(db, org_id, me.id, allowed={"owner", "admin"})
    api_key = revoke_api_key(db, org_id, key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    return api_key

