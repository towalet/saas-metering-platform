"""
Sliding-window rate limiter backed by Redis.

Algorithm (fixed-window with per-second granularity):
  1. Build a Redis key: rl:{api_key_id}:{window_start} where window_start = current unix timestamp truncated to 60s boundary.
  2. INCR the key.
  3. If the key is new (count == 1), set EXPIRE to 120s (safety margin).
  4. If count > limit, reject with 429.

The limit is configurable per-org via the `rate_limit_rpm` column.

Response headers (added to every API-key-authed response):
  X-RateLimit-Limit:     the max requests allowed per window
  X-RateLimit-Remaining: how many requests are left in the current window
  X-RateLimit-Reset:     unix timestamp when the current window expires
"""

import time
from dataclasses import dataclass

import redis as sync_redis


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: int  # unix timestamp

def check_rate_limit(
    redis_client: sync_redis.Redis,
    key_id: int,
    limit: int,
    window_seconds: int = 60,
) -> RateLimitResult:
    """
    Check and increment the rate limit counter for an API key.

    Returns a RateLimitResult indicating whether the request is allowed
    and the current rate limit state for response headers.
    """
    # Determine the current window based on the current time and window size
    now = int(time.time())
    # The window is defined by the start time (truncated to the nearest window) and end time
    window_start = now - (now % window_seconds)
    # The window end is just the start plus the window size
    window_end = window_start + window_seconds
    redis_key = f"rl:{key_id}:{window_start}"

    # Atomic increment
    current_count = redis_client.incr(redis_key)

    # Set expiry on first request in this window
    if current_count == 1:
        redis_client.expire(redis_key, window_seconds * 2)

    # Calculate remaining requests and whether the request is allowed
    remaining = max(0, limit - current_count)
    allowed = current_count <= limit

    # Rate limit state for response headers
    return RateLimitResult(
        allowed=allowed,
        limit=limit,
        remaining=remaining,
        reset_at=window_end,
    )

