from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from app.config import settings

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def get_json(key: str) -> Any | None:
    redis = await get_redis()
    payload = await redis.get(key)
    return json.loads(payload) if payload else None


async def set_json(key: str, value: Any, ttl: int | None = None) -> None:
    redis = await get_redis()
    await redis.set(key, json.dumps(value, default=str), ex=ttl or settings.cache_ttl_seconds)


async def delete(key: str) -> None:
    redis = await get_redis()
    await redis.delete(key)
