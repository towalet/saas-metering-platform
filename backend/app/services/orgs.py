from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.orgs import Org
from app.models.org_member import OrgMember
from app.models.user import User

# This file contains service functions related to organizations and their members.
VALID_ROLES = {"owner", "admin", "member"}

# Create a new org and add the owner as a member
def create_org(db: Session, owner_user: User, name: str) -> Org:
    org = Org(name=name)
    db.add(org)
    db.flush()  # get org.id

    membership = OrgMember(org_id=org.id, user_id=owner_user.id, role="owner")
    db.add(membership)

    db.commit()
    db.refresh(org)
    return org

# List all orgs a user is a member of, ordered by most recently created first
def list_user_orgs(db: Session, user_id: int) -> list[Org]:
    stmt = (
        select(Org)
        .join(OrgMember, OrgMember.org_id == Org.id)
        .where(OrgMember.user_id == user_id)
        .order_by(Org.created_at.desc(), Org.id.desc())
    )
    return list(db.execute(stmt).scalars().all())

# Get a user's membership in an org, or None if not a member
def get_membership(db: Session, org_id: int, user_id: int) -> OrgMember | None:
    stmt = select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()

def count_org_owners(db: Session, org_id: int, exclude_user_id: int | None = None) -> int:
    stmt = select(func.count()).select_from(OrgMember).where(
        OrgMember.org_id == org_id,
        OrgMember.role == "owner",
    )
    if exclude_user_id is not None:
        stmt = stmt.where(OrgMember.user_id != exclude_user_id)
    return db.execute(stmt).scalar_one()

# Add a member to an org by email. If the user doesn't exist, raises LookupError. If the role is invalid, raises ValueError.
# If the actor is not an owner, raising PermissionError when attempting to grant/revoke owner.
def add_member_by_email(db: Session, org_id: int, email: str, role: str, actor_role: str) -> tuple[OrgMember, User]:
    if role not in VALID_ROLES:
        raise ValueError("Invalid role")

    if role == "owner" and actor_role != "owner":
        raise PermissionError("Only owners can grant owner role")

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        raise LookupError("User not found")

    existing = get_membership(db, org_id, user.id)
    if existing:
        if actor_role != "owner" and existing.role == "owner" and role != "owner":
            raise PermissionError("Only owners can revoke owner role")

        if existing.role == "owner" and role != "owner":
            remaining_owners = count_org_owners(db, org_id, exclude_user_id=existing.user_id)
            if remaining_owners == 0:
                raise ValueError("Org must have at least one owner")

        # update role if already exists
        existing.role = role
        db.commit()
        db.refresh(existing)
        return existing, user

    membership = OrgMember(org_id=org_id, user_id=user.id, role=role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership, user
