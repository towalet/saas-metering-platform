from sqlalchemy import ForeignKey, String, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

# Represents a user's membership in an organization, including their role (owner, admin, member).
class OrgMember(Base):
    __tablename__ = "org_members"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # "owner" | "admin" | "member"
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member")

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    org = relationship("Org", back_populates="members")
    user = relationship("User", back_populates="org_memberships")
