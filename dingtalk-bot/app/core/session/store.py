"""会话存储抽象层。

支持 MemoryStore（开发/测试）和 RedisStore（生产）。
"""

from __future__ import annotations

import abc
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.session import Session


class SessionStore(abc.ABC):
    """会话存储基类。"""

    @abc.abstractmethod
    async def get(self, session_id: str) -> Session | None:
        """获取会话。"""

    @abc.abstractmethod
    async def set(self, session: Session, ttl_seconds: int) -> None:
        """保存会话（含过期时间）。"""

    @abc.abstractmethod
    async def delete(self, session_id: str) -> None:
        """删除会话。"""

    @abc.abstractmethod
    async def exists(self, session_id: str) -> bool:
        """检查会话是否存在。"""

    @abc.abstractmethod
    async def clear_all(self) -> None:
        """清空所有会话。"""

    @abc.abstractmethod
    async def count(self) -> int:
        """获取会话总数。"""

    @abc.abstractmethod
    async def list_ids(self, limit: int = 100, offset: int = 0) -> list[str]:
        """列出会话 ID。"""

    @abc.abstractmethod
    async def evict_expired(self) -> int:
        """清理过期会话，返回清理数量。"""


class MemoryStore(SessionStore):
    """内存会话存储（开发/测试用）。"""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._expires_at: dict[str, float] = {}

    async def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None

        # 检查是否过期
        expires_at = self._expires_at.get(session_id, float("inf"))
        if time.time() > expires_at:
            await self.delete(session_id)
            return None

        return session

    async def set(self, session: Session, ttl_seconds: int) -> None:
        self._sessions[session.session_id] = session
        self._expires_at[session.session_id] = time.time() + ttl_seconds

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._expires_at.pop(session_id, None)

    async def exists(self, session_id: str) -> bool:
        return session_id in self._sessions and (
            time.time() <= self._expires_at.get(session_id, float("inf"))
        )

    async def clear_all(self) -> None:
        self._sessions.clear()
        self._expires_at.clear()

    async def count(self) -> int:
        return len(self._sessions)

    async def list_ids(self, limit: int = 100, offset: int = 0) -> list[str]:
        ids = list(self._sessions.keys())
        return ids[offset : offset + limit]

    async def evict_expired(self) -> int:
        now = time.time()
        expired = [
            sid
            for sid, exp in self._expires_at.items()
            if now > exp
        ]
        for sid in expired:
            await self.delete(sid)
        return len(expired)
