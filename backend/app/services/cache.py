"""Redis-backed cache with fail-open behaviour.

Every helper degrades gracefully: if Redis is unavailable the application keeps
working (cache misses, open rate limiting) instead of failing user requests.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Process-wide lazy singleton around a Redis client."""

    _instance: "RedisCache | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "RedisCache":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._client: redis.Redis | None = None
                    instance._client_lock = threading.Lock()
                    cls._instance = instance
        return cls._instance

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    settings = get_settings()
                    self._client = redis.Redis.from_url(
                        settings.REDIS_URL,
                        decode_responses=True,
                        socket_timeout=2,
                        socket_connect_timeout=2,
                    )
        return self._client

    def ping(self) -> bool:
        """Return True when Redis answers PING; False on any failure."""
        try:
            return bool(self._get_client().ping())
        except Exception:  # noqa: BLE001 - fail-open by design
            return False

    def get_json(self, key: str) -> Any | None:
        """Fetch a JSON value; returns None on miss or Redis failure."""
        try:
            raw = self._get_client().get(key)
            return json.loads(raw) if raw else None
        except Exception:  # noqa: BLE001
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        """Store a JSON value with a TTL; returns False when Redis is down."""
        try:
            ttl = ttl_seconds or get_settings().CACHE_TTL_SECONDS
            self._get_client().set(key, json.dumps(value, default=str), ex=ttl)
            return True
        except Exception:  # noqa: BLE001
            return False

    def delete(self, *keys: str) -> None:
        try:
            self._get_client().delete(*keys)
        except Exception:  # noqa: BLE001
            pass

    def incr_with_expiry(self, key: str, window_seconds: int = 90) -> int | None:
        """Atomically increment a counter (rate limiting); None when Redis is down."""
        try:
            client = self._get_client()
            count = client.incr(key)
            if count == 1:
                client.expire(key, window_seconds)
            return int(count)
        except Exception:  # noqa: BLE001
            return None


redis_cache = RedisCache()
