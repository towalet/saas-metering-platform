"""
API Key model.

Security design:
- The full plaintext key is returned to the user ONCE at creation time.
- Only the SHA-256 hash is stored in the database.
- A short prefix (first 8 chars) is stored so users can identify keys in the UI without exposing the secret.
- When a request arrives with X-API-Key, we hash it and look up the hash.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Which org owns this key
    org_id: Mapped[int] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Human-readable label, e.g. "Production Backend", "CI Runner"
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # First 8 chars of the plaintext key, e.g. "smp_live", safe to display
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)

    # SHA-256 hex digest of the full key, this is what we query against.
    # Indexed + unique so lookups are O(1) and duplicates are impossible.
    key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    # Soft-delete: revoking a key sets this to False rather than deleting the row.
    # This preserves audit history (usage events still reference this key).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Optional expiration, null means the key never expires
    expires_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Updated every time the key is used to authenticate a request
    last_used_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships 
    org = relationship("Org", back_populates="api_keys")

