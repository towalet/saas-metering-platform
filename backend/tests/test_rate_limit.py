"""Tests for the sliding-window rate limiter."""

import pytest

from app.core.rate_limit import check_rate_limit, RateLimitResult


class FakeRedis:
    """Minimal in-memory Redis substitute for testing."""

    def __init__(self):
        self._store: dict[str, int] = {}
        self._expiries: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    def expire(self, key: str, seconds: int) -> None:
        self._expiries[key] = seconds

    def get(self, key: str) -> str | None:
        val = self._store.get(key)
        return str(val) if val is not None else None


class TestSlidingWindowRateLimit:
    def test_first_request_allowed(self):
        r = FakeRedis()
        result = check_rate_limit(r, key_id=1, limit=5)
        assert result.allowed is True
        assert result.remaining == 4
        assert result.limit == 5

    def test_limit_reached_blocks(self):
        """After exactly `limit` requests, the next one is blocked."""
        r = FakeRedis()
        limit = 3
        for _ in range(limit):
            result = check_rate_limit(r, key_id=1, limit=limit)
            assert result.allowed is True

        # This should be the 4th request
        result = check_rate_limit(r, key_id=1, limit=limit)
        assert result.allowed is False
        assert result.remaining == 0

    def test_remaining_decreases(self):
        r = FakeRedis()
        limit = 5
        for i in range(limit):
            result = check_rate_limit(r, key_id=1, limit=limit)
            assert result.remaining == limit - (i + 1)

    def test_different_keys_independent(self):
        """Rate limits for different API keys should not interfere."""
        r = FakeRedis()
        for _ in range(5):
            check_rate_limit(r, key_id=1, limit=5)

        # key_id=1 is now at limit, but key_id=2 should be fresh
        result_1 = check_rate_limit(r, key_id=1, limit=5)
        result_2 = check_rate_limit(r, key_id=2, limit=5)
        assert result_1.allowed is False
        assert result_2.allowed is True
        assert result_2.remaining == 4

    def test_reset_timestamp_is_future(self):
        import time
        r = FakeRedis()
        result = check_rate_limit(r, key_id=1, limit=10)
        assert result.reset_at > int(time.time()) - 1

    def test_expiry_set_on_first_request(self):
        r = FakeRedis()
        check_rate_limit(r, key_id=1, limit=10, window_seconds=60)
        # Verify that at least one key had expire called
        assert len(r._expiries) > 0
        for ttl in r._expiries.values():
            assert ttl == 120  # 2x window

