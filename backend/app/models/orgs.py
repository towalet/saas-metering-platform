from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

# This file defines the Org model, which represents an organization in the system. Each organization has a unique ID, a name, and a timestamp for when it was created. The Org model also has a relationship with the OrgMember model, which represents the members of the organization.
class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members = relationship("OrgMember", back_populates="org", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="org", cascade="all, delete-orphan")
