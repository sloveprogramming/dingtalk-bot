"""会话管理单元测试。"""

from __future__ import annotations

import pytest

from app.core.session.manager import SessionManager
from app.core.session.store import MemoryStore
from app.models.session import Session


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def manager(store: MemoryStore) -> SessionManager:
    return SessionManager(
        store=store,
        ttl_minutes=30,
        max_context_tokens=1000,
    )


class TestMemoryStore:
    """MemoryStore 基本功能测试。"""

    async def test_set_and_get(self, store: MemoryStore):
        session = Session(
            session_id="test_sid",
            conversation_type="1",
            user_id="user1",
        )
        await store.set(session, ttl_seconds=300)
        retrieved = await store.get("test_sid")
        assert retrieved is not None
        assert retrieved.session_id == "test_sid"
        assert retrieved.user_id == "user1"

    async def test_get_expired(self, store: MemoryStore):
        session = Session(session_id="expired", conversation_type="1", user_id="u1")
        await store.set(session, ttl_seconds=-1)  # 立即过期
        retrieved = await store.get("expired")
        assert retrieved is None

    async def test_delete(self, store: MemoryStore):
        session = Session(session_id="del", conversation_type="1", user_id="u1")
        await store.set(session, ttl_seconds=300)
        await store.delete("del")
        assert await store.get("del") is None

    async def test_exists(self, store: MemoryStore):
        session = Session(session_id="exist", conversation_type="1", user_id="u1")
        await store.set(session, ttl_seconds=300)
        assert await store.exists("exist") is True
        await store.delete("exist")
        assert await store.exists("exist") is False

    async def test_clear_all(self, store: MemoryStore):
        for i in range(3):
            s = Session(session_id=f"s{i}", conversation_type="1", user_id="u1")
            await store.set(s, ttl_seconds=300)
        await store.clear_all()
        assert await store.count() == 0

    async def test_evict_expired(self, store: MemoryStore):
        s1 = Session(session_id="fresh", conversation_type="1", user_id="u1")
        s2 = Session(session_id="stale", conversation_type="1", user_id="u1")
        await store.set(s1, ttl_seconds=300)
        await store.set(s2, ttl_seconds=-1)
        evicted = await store.evict_expired()
        assert evicted == 1
        assert await store.get("fresh") is not None
        assert await store.get("stale") is None

    async def test_list_ids(self, store: MemoryStore):
        for i in range(5):
            s = Session(session_id=f"list_{i}", conversation_type="1", user_id="u1")
            await store.set(s, ttl_seconds=300)
        ids = await store.list_ids(limit=3, offset=1)
        assert len(ids) == 3


class TestSessionManager:
    """SessionManager 功能测试。"""

    async def test_get_or_create_new(self, manager: SessionManager):
        session = await manager.get_or_create(
            conversation_id="cid1",
            user_id="user1",
            conversation_type="1",
            user_nick="张三",
        )
        assert session.session_id == "cid1"
        assert session.user_id == "user1"
        assert session.user_nick == "张三"
        assert session.message_count == 0

    async def test_get_or_create_existing(self, manager: SessionManager):
        s1 = await manager.get_or_create(
            conversation_id="cid2",
            user_id="user1",
        )
        s2 = await manager.get_or_create(
            conversation_id="cid2",
            user_id="user1",
        )
        assert s1 is s2  # 同一对象

    async def test_add_message(self, manager: SessionManager):
        session = await manager.get_or_create(
            conversation_id="cid3",
            user_id="user1",
        )
        updated = await manager.add_message(
            session_id="cid3",
            role="user",
            content="你好",
            token_count=10,
        )
        assert updated.message_count == 1
        assert updated.history[0].role == "user"
        assert updated.history[0].content == "你好"

    async def test_add_message_nonexistent_session(self, manager: SessionManager):
        with pytest.raises(ValueError):
            await manager.add_message("nonexistent", "user", "hello")

    async def test_get_context_trimmed(self, manager: SessionManager):
        """上下文裁剪：超出 Token 预算时丢弃最早的消息。"""
        session = await manager.get_or_create(
            conversation_id="trim_test",
            user_id="user1",
        )
        # max_context_tokens=1000，每条 600 tokens，
        # 加 2 条会超预算，应裁剪为仅保留最后 1 条
        await manager.add_message("trim_test", "user", "msg1", token_count=600)
        await manager.add_message("trim_test", "user", "msg2", token_count=600)

        context = await manager.get_context("trim_test")
        assert len(context) == 1
        assert context[0].content == "msg2"

    async def test_get_context_no_trim(self, manager: SessionManager):
        """未超出预算时上下文明完整。"""
        session = await manager.get_or_create(
            conversation_id="no_trim",
            user_id="user1",
        )
        await manager.add_message("no_trim", "user", "hello", token_count=100)
        await manager.add_message("no_trim", "assistant", "hi", token_count=200)
        context = await manager.get_context("no_trim")
        assert len(context) == 2

    async def test_get_context_empty_session(self, manager: SessionManager):
        context = await manager.get_context("nonexistent")
        assert context == []

    async def test_clear(self, manager: SessionManager):
        await manager.get_or_create(conversation_id="clear_me", user_id="user1")
        await manager.clear("clear_me")
        context = await manager.get_context("clear_me")
        assert context == []

    async def test_clear_all(self, manager: SessionManager):
        for i in range(3):
            await manager.get_or_create(conversation_id=f"cid{i}", user_id="user1")
        await manager.clear_all()
        stats = await manager.get_stats()
        assert stats["total_sessions"] == 0

    async def test_get_stats(self, manager: SessionManager):
        await manager.get_or_create(conversation_id="stats_test", user_id="user1")
        stats = await manager.get_stats()
        assert stats["total_sessions"] >= 1
        assert stats["backend"] == "MemoryStore"
