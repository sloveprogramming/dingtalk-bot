"""Redis 会话存储（生产环境用）。"""

from __future__ import annotations

import json
import pickle
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.session.store import SessionStore
from app.models.session import Session
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RedisStore(SessionStore):
    """基于 Redis 的会话存储。

    使用 Redis String 存储序列化的 Session 对象，
    配合 TTL 实现会话自动过期。
    """

    KEY_PREFIX = "session:"

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis: aioredis.Redis | None = None
        self._redis_url = redis_url
        self._connected = False

    async def _get_redis(self) -> aioredis.Redis:
        """懒连接 Redis。"""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=False,
            )
            try:
                await self._redis.ping()
                self._connected = True
                logger.info("Redis 连接成功: %s", self._redis_url)
            except Exception as exc:
                logger.warning("Redis 连接失败: %s", exc)
                self._connected = False
        return self._redis

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            self._connected = False
            logger.info("Redis 连接已关闭")

    def _key(self, session_id: str) -> str:
        return f"{self.KEY_PREFIX}{session_id}"

    @staticmethod
    def _serialize(session: Session) -> bytes:
        """序列化 Session。"""
        return pickle.dumps(session)

    @staticmethod
    def _deserialize(data: bytes) -> Session:
        """反序列化 Session。"""
        return pickle.loads(data)

    async def get(self, session_id: str) -> Session | None:
        try:
            redis = await self._get_redis()
            data = await redis.get(self._key(session_id))
            if data is None:
                return None
            return self._deserialize(data)
        except Exception as exc:
            logger.error("Redis 获取会话失败: %s", exc)
            return None

    async def set(self, session: Session, ttl_seconds: int) -> None:
        try:
            redis = await self._get_redis()
            data = self._serialize(session)
            await redis.setex(self._key(session.session_id), ttl_seconds, data)
        except Exception as exc:
            logger.error("Redis 保存会话失败: %s", exc)

    async def delete(self, session_id: str) -> None:
        try:
            redis = await self._get_redis()
            await redis.delete(self._key(session_id))
        except Exception as exc:
            logger.error("Redis 删除会话失败: %s", exc)

    async def exists(self, session_id: str) -> bool:
        try:
            redis = await self._get_redis()
            return bool(await redis.exists(self._key(session_id)))
        except Exception as exc:
            logger.error("Redis 检查会话失败: %s", exc)
            return False

    async def clear_all(self) -> None:
        try:
            redis = await self._get_redis()
            cursor = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor, match=f"{self.KEY_PREFIX}*", count=100
                )
                if keys:
                    await redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            logger.error("Redis 清空会话失败: %s", exc)

    async def count(self) -> int:
        try:
            redis = await self._get_redis()
            cursor = 0
            count = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor, match=f"{self.KEY_PREFIX}*", count=100
                )
                count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception as exc:
            logger.error("Redis 统计会话失败: %s", exc)
            return 0

    async def list_ids(self, limit: int = 100, offset: int = 0) -> list[str]:
        try:
            redis = await self._get_redis()
            cursor = 0
            all_keys: list[bytes] = []
            while True:
                cursor, keys = await redis.scan(
                    cursor, match=f"{self.KEY_PREFIX}*", count=limit * 2
                )
                all_keys.extend(keys)
                if cursor == 0 or len(all_keys) >= offset + limit:
                    break
            all_keys = sorted(all_keys)
            selected = all_keys[offset : offset + limit]
            prefix_len = len(self.KEY_PREFIX)
            return [key.decode().split(":")[1] for key in selected]
        except Exception as exc:
            logger.error("Redis 列出会话失败: %s", exc)
            return []

    async def evict_expired(self) -> int:
        # Redis TTL 自动过期，无需手动清理
        return 0
