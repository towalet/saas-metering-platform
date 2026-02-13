"""
Redis connection pool.

Provides a single shared Redis client for the application.
Used by rate limiting and potentially caching later.
"""

import os

import redis.asyncio as aioredis
import redis as sync_redis

# Redis connection URL
def _redis_url() -> str:
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    return f"redis://{host}:{port}/0"


# Synchronous client (used by FastAPI sync endpoints / dependencies)
_sync_pool: sync_redis.Redis | None = None

# Get the shared synchronous Redis client (lazy-initialised)
def get_redis() -> sync_redis.Redis:
    """Return a shared synchronous Redis client (lazy-initialised)."""
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = sync_redis.from_url(
            _redis_url(),
            decode_responses=True,
            socket_connect_timeout=2,
        )
    return _sync_pool

# Close the Redis connection pool on app shutdown
def close_redis() -> None:
    """Shutdown the Redis connection pool (call on app shutdown)."""
    global _sync_pool
    if _sync_pool is not None:
        _sync_pool.close()
        _sync_pool = None

