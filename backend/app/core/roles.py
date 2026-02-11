from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.services.orgs import get_membership

def require_org_role(db: Session, org_id: int, user_id: int, allowed: set[str]) -> str:
    membership = get_membership(db, org_id, user_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Org not found or no access")
    if membership.role not in allowed:
        raise HTTPException(status_code=403, detail="Insufficient role")
    return membership.role
