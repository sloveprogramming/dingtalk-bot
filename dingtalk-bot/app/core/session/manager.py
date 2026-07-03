"""会话管理器 —— 会话 CRUD、上下文修剪、TTL 过期清理。"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.session import MessageEntry, Session
from app.core.session.store import SessionStore


class SessionManager:
    """会话管理器。

    负责:
    - 会话的创建、读取、更新
    - 上下文窗口滑窗修剪（按 Token 预算）
    - TTL 过期清理
    """

    def __init__(
        self,
        store: SessionStore,
        ttl_minutes: int = 30,
        max_context_tokens: int = 100_000,
    ) -> None:
        self._store = store
        self._ttl = timedelta(minutes=ttl_minutes)
        self._max_context_tokens = max_context_tokens

    # ── 公开接口 ──────────────────────────────────────────

    async def get_or_create(
        self,
        conversation_id: str,
        user_id: str,
        conversation_type: str = "1",
        user_nick: str = "",
    ) -> Session:
        """获取或创建会话。

        Args:
            conversation_id: 会话 ID（来自钉钉）。
            user_id: 用户 UserId。
            conversation_type: 会话类型。
            user_nick: 用户昵称。

        Returns:
            已存在的会话（若未过期），否则返回新会话。
        """
        session = await self._store.get(conversation_id)
        if session is not None:
            return session

        session = Session(
            session_id=conversation_id,
            conversation_type=conversation_type,
            user_id=user_id,
            user_nick=user_nick,
        )
        await self._save(session)
        return session

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        token_count: int = 0,
    ) -> Session:
        """向会话中添加一条消息。

        Args:
            session_id: 会话 ID。
            role: user / assistant / system。
            content: 消息内容。
            token_count: 估算 Token 数。

        Returns:
            更新后的会话。
        """
        session = await self._store.get(session_id)
        if session is None:
            raise ValueError(f"会话不存在: {session_id}")

        session.add_message(role=role, content=content, token_count=token_count)
        await self._save(session)
        return session

    async def get_context(self, session_id: str) -> list[MessageEntry]:
        """获取会话上下文（已按 Token 预算裁剪）。

        从最新的消息开始保留，直到达到 max_context_tokens 预算。

        Args:
            session_id: 会话 ID。

        Returns:
            裁剪后的消息列表（按时间正序）。
        """
        session = await self._store.get(session_id)
        if session is None:
            return []

        return self._trim_context(session.history, self._max_context_tokens)

    async def clear(self, session_id: str) -> None:
        """清除指定会话。"""
        await self._store.delete(session_id)

    async def clear_all(self) -> None:
        """清除所有会话。"""
        await self._store.clear_all()

    async def get_stats(self) -> dict:
        """获取会话统计。"""
        return {
            "total_sessions": await self._store.count(),
            "backend": self._store.__class__.__name__,
            "ttl_minutes": self._ttl.total_seconds() / 60,
            "max_context_tokens": self._max_context_tokens,
        }

    async def evict_expired(self) -> int:
        """清理过期会话。

        Returns:
            被清理的会话数量。
        """
        return await self._store.evict_expired()

    # ── 内部方法 ──────────────────────────────────────────

    async def _save(self, session: Session) -> None:
        """保存会话（自动设置 TTL）。"""
        await self._store.set(session, int(self._ttl.total_seconds()))

    @staticmethod
    def _trim_context(
        history: list[MessageEntry],
        max_tokens: int,
    ) -> list[MessageEntry]:
        """按 Token 预算裁剪消息历史（滑窗，保留最新的消息）。

        Args:
            history: 完整消息历史（按时间正序）。
            max_tokens: Token 预算上限。

        Returns:
            裁剪后的消息列表（仍按时间正序）。
        """
        if not history:
            return []

        total = sum(entry.token_count for entry in history)
        if total <= max_tokens:
            return list(history)

        # 从后往前累加，直到达到预算
        cumulative = 0
        for i in range(len(history) - 1, -1, -1):
            cumulative += history[i].token_count
            if cumulative > max_tokens:
                return list(history[i + 1 :])

        return list(history)
