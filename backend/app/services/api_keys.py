"""
Service layer for API key management.

Key security flow:
  1. Generate 32 random hex bytes via `secrets` (cryptographically secure).
  2. Prepend the prefix `smp_live_` so leaked keys are identifiable by scanners.
  3. SHA-256 hash the full key for storage (never store plaintext).
  4. Return the plaintext to the caller ONCE.  After this it cannot be recovered.
  5. On incoming requests, hash the provided key and look up the hash in the DB.
"""

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey

# Constants 
KEY_PREFIX_TAG = "smp_live_"  # identifiable prefix for leak scanners
KEY_RANDOM_BYTES = 32         # 32 hex bytes = 64 hex chars of entropy


# Internal helpers 
def _generate_raw_key() -> str:
    """Generate a full plaintext API key like 'smp_live_a1b2c3d4...'."""
    random_part = secrets.token_hex(KEY_RANDOM_BYTES)
    return f"{KEY_PREFIX_TAG}{random_part}"


def hash_key(plaintext: str) -> str:
    """SHA-256 hash a plaintext key.  Used at creation and at lookup time."""
    # Return the hex digest
    return hashlib.sha256(plaintext.encode()).hexdigest()


# Public service functions
def create_api_key(db: Session, org_id: int, name: str) -> tuple[ApiKey, str]:
    """
    Create a new API key for an org.

    Returns (api_key_row, plaintext_key).
    The plaintext is NOT stored -- this is the only time it is available.
    """
    # Generate the key
    plaintext = _generate_raw_key()
    # Create DB row
    prefix = plaintext[:12]  # e.g. "smp_live_a1b2"
    # the SHA-256 hash of the full key
    hashed = hash_key(plaintext)

    # Create and store the ApiKey row
    api_key = ApiKey(
        org_id=org_id,
        name=name,
        key_prefix=prefix,
        key_hash=hashed,
    )
    # Save to DB
    db.add(api_key)
    # Commit transaction
    db.commit()
    # Refresh to get ID populated
    db.refresh(api_key)
    return api_key, plaintext


def list_api_keys(db: Session, org_id: int) -> list[ApiKey]:
    """List all API keys for an org (active and revoked)."""
    # Query all keys for the org, ordered by creation date descending
    stmt = (
        select(ApiKey)
        .where(ApiKey.org_id == org_id)
        .order_by(ApiKey.created_at.desc())
    )
    # Return the list
    return list(db.execute(stmt).scalars().all())


def revoke_api_key(db: Session, org_id: int, key_id: int) -> ApiKey | None:
    """
    Soft-revoke an API key by setting is_active = False.

    Returns the key if found and revoked, None if not found or wrong org.
    We do NOT hard-delete so usage history is preserved.
    """
    # Look up the key by ID and org
    stmt = select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id)
    # This will be None if the key doesn't exist or belongs to a different org
    api_key = db.execute(stmt).scalar_one_or_none()
    if not api_key:
        return None
    # Soft-revoke
    api_key.is_active = False
    db.commit()
    db.refresh(api_key)
    return api_key


def get_key_by_hash(db: Session, key_hash: str) -> ApiKey | None:
    """
    Look up an active, non-expired API key by its hash.

    This is called on every API-key-authenticated request:
      1. Hash the incoming plaintext key.
      2. Query this function.
      3. If None -> 401.

    Also updates last_used_at so the org admin can see when each key was last used.
    """
    # Query for an active key matching the hash
    stmt = select(ApiKey).where(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active.is_(True),
    )
    # This will be None if no active key matches
    api_key = db.execute(stmt).scalar_one_or_none()
    if not api_key:
        return None

    # Check expiration
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        return None

    # Touch last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(api_key)
    return api_key

