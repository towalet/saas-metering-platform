from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.orgs import OrgCreateIn, OrgOut, OrgMemberAddIn, OrgMemberOut
from app.services.orgs import create_org, list_user_orgs, add_member_by_email
from app.core.roles import require_org_role

# This file contains API endpoints related to organizations and their members.

# The endpoints in this file generally require the user to be authenticated, and some require the user to have a certain role in the org (owner/admin).
router = APIRouter(prefix="/orgs", tags=["orgs"])

# Create a new org. The authenticated user will be the owner.
@router.post("", response_model=OrgOut, status_code=201)
def create_org_endpoint(payload: OrgCreateIn, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    return create_org(db, me, payload.name)

# List all orgs the authenticated user is a member of, ordered by most recently created first
@router.get("", response_model=list[OrgOut])
def list_orgs_endpoint(db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    return list_user_orgs(db, me.id)

# Add a member to an org by email. The authenticated user must be an owner or admin of the org.
@router.post("/{org_id}/members", response_model=OrgMemberOut, status_code=201)
def add_member_endpoint(
    org_id: int,
    payload: OrgMemberAddIn,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    actor_role = require_org_role(db, org_id, me.id, allowed={"owner", "admin"})
    try:
        m, user = add_member_by_email(db, org_id, payload.email, payload.role, actor_role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    # return email for convenience
    return OrgMemberOut(user_id=m.user_id, email=user.email, role=m.role)
