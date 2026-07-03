"""FastAPI 依赖注入工厂。

提供全局单例组件的依赖注入函数。
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Request

from app.config import Settings
from app.core.dingtalk.client import DingTalkClient
from app.core.llm.base import LLMProvider
from app.core.llm.factory import build_llm_provider
from app.core.message.handler import MessageHandler
from app.core.message.plugins.echo import EchoPlugin
from app.core.message.plugins.help import HelpPlugin
from app.core.message.plugins.llm_chat import LLMChatPlugin
from app.core.message.plugins.register import PluginRegistry
from app.core.session.manager import SessionManager
from app.core.session.store import MemoryStore, SessionStore
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_settings(request: Request) -> Settings:
    """获取应用配置。"""
    return request.app.state.settings


async def get_dingtalk_client(request: Request) -> AsyncGenerator[DingTalkClient, None]:
    """获取 DingTalk API 客户端（单例）。"""
    client: DingTalkClient | None = getattr(request.app.state, "dingtalk_client", None)
    if client is None:
        settings = request.app.state.settings
        client = DingTalkClient(
            app_key=settings.dingtalk.app_key,
            app_secret=settings.dingtalk.app_secret,
            bot_code=settings.dingtalk.bot_code,
        )
        request.app.state.dingtalk_client = client
    yield client


async def get_session_store(request: Request) -> AsyncGenerator[SessionStore, None]:
    """获取会话存储后端。"""
    settings = request.app.state.settings
    store: SessionStore | None = getattr(request.app.state, "session_store", None)
    if store is None:
        if settings.session.backend == "redis":
            from app.core.session.store_redis import RedisStore

            store = RedisStore(redis_url=settings.session.redis_url or "")
        else:
            store = MemoryStore()
        request.app.state.session_store = store
    yield store


async def get_session_manager(
    request: Request,
) -> AsyncGenerator[SessionManager, None]:
    """获取会话管理器。"""
    mgr: SessionManager | None = getattr(request.app.state, "session_manager", None)
    if mgr is None:
        settings = request.app.state.settings
        store = await anext(get_session_store(request))
        mgr = SessionManager(
            store=store,
            ttl_minutes=settings.session.ttl_minutes,
            max_context_tokens=settings.session.max_context_tokens,
        )
        request.app.state.session_manager = mgr
    yield mgr


async def get_llm_provider(request: Request) -> LLMProvider | None:
    """获取 LLM 提供者（可能为 None）。"""
    provider: LLMProvider | None = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        settings = request.app.state.settings
        if settings.llm.anthropic_api_key:
            provider = build_llm_provider(settings.llm)
            request.app.state.llm_provider = provider
    return provider


def get_plugin_registry(request: Request) -> PluginRegistry:
    """获取插件注册器（单例）。"""
    registry: PluginRegistry | None = getattr(
        request.app.state, "plugin_registry", None
    )
    if registry is None:
        registry = PluginRegistry()
        registry.register(EchoPlugin())
        registry.register(HelpPlugin())
        registry.register(LLMChatPlugin())
        request.app.state.plugin_registry = registry
    return registry