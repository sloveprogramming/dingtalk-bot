"""FastAPI 应用入口。

启动时自动初始化所有全局组件：
- HTTP 回调端点（健康检查 + 管理 API）
- DingTalk Stream 长连接（接收消息，无需公网端口）
- LLM 提供者、会话管理、插件系统
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.health import router as health_router
from app.api.webhook import router as webhook_router
from app.config import Settings
from app.core.dingtalk.client import DingTalkClient
from app.core.llm.factory import build_llm_provider
from app.core.message.handler import MessageHandler
from app.core.message.plugins.echo import EchoPlugin
from app.core.message.plugins.help import HelpPlugin
from app.core.message.plugins.llm_chat import LLMChatPlugin
from app.core.message.plugins.register import PluginRegistry
from app.core.session.manager import SessionManager
from app.core.session.store import MemoryStore
from app.core.session.store_redis import RedisStore
from app.dingtalk_stream import DingTalkStreamBot
from app.group_events import GroupEventHandler
from app.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # ═══ 启动 ════════════════════════════════════════════
    settings = Settings()
    setup_logging(settings.log_level)
    app.state.settings = settings
    stream_task: asyncio.Task | None = None

    # 1. DingTalk API 客户端（发送消息用）
    dingtalk_client = DingTalkClient(
        app_key=settings.dingtalk.app_key,
        app_secret=settings.dingtalk.app_secret,
        bot_code=settings.dingtalk.bot_code,
    )
    app.state.dingtalk_client = dingtalk_client
    logger.info("DingTalk 客户端已初始化")

    # 2. 会话存储
    if settings.session.backend == "redis" and settings.session.redis_url:
        session_store = RedisStore(redis_url=settings.session.redis_url)
    else:
        session_store = MemoryStore()
    app.state.session_store = session_store

    # 3. 会话管理器
    session_manager = SessionManager(
        store=session_store,
        ttl_minutes=settings.session.ttl_minutes,
        max_context_tokens=settings.session.max_context_tokens,
    )
    app.state.session_manager = session_manager
    logger.info("会话管理器已初始化 (backend=%s)", settings.session.backend)

    # 4. LLM 提供者
    llm_provider = None
    if settings.llm.anthropic_api_key:
        llm_provider = build_llm_provider(settings.llm)
        app.state.llm_provider = llm_provider
        logger.info(
            "LLM 提供者已初始化: %s (%s)",
            settings.llm.provider,
            settings.llm.anthropic_model,
        )
    else:
        msg = "LLM API 密钥未配置，智能对话功能将不可用"
        logger.warning(msg)

    # 5. 插件注册
    registry = PluginRegistry()
    registry.register(EchoPlugin())
    registry.register(HelpPlugin())
    registry.register(LLMChatPlugin())
    app.state.plugin_registry = registry
    logger.info("插件注册完成: %d 个", len(registry.list_plugins()))

    # 6. 构建消息处理器
    message_handler = MessageHandler(
        registry=registry,
        dingtalk_client=dingtalk_client,
        session_manager=session_manager,
        llm_provider=llm_provider,
        settings=settings,
    )
    app.state.message_handler = message_handler

    # 7. 启动 Stream 模式连接（长连接接收消息）
    if settings.dingtalk.app_key and settings.dingtalk.app_secret:
        # 创建群聊事件监听器
        group_handler = GroupEventHandler(dingtalk_client=dingtalk_client)
        app.state.group_handler = group_handler

        stream_bot = DingTalkStreamBot(
            client_id=settings.dingtalk.app_key,
            client_secret=settings.dingtalk.app_secret,
            message_handler=message_handler,
            event_handler=group_handler,
            authorized_users=settings.authorized_users,
        )
        app.state.stream_bot = stream_bot
        # 启动 Stream 异步连接
        stream_task = asyncio.create_task(stream_bot.start())
        logger.info("Stream 客户端正在连接...")
    else:
        logger.warning("钉钉 AppKey/Secret 未配置，Stream 模式未启动")

    yield

    # ═══ 关闭 ════════════════════════════════════════════
    logger.info("正在关闭服务...")

    # 关闭 Stream 连接
    if stream_task is not None:
        stream_task.cancel()
        try:
            await stream_task
        except (asyncio.CancelledError, Exception):
            pass
    if hasattr(app.state, "stream_bot"):
        await app.state.stream_bot.stop()
    logger.info("Stream 客户端已停止")

    # 关闭 DingTalk API 客户端
    if dingtalk_client:
        await dingtalk_client.close()

    # 关闭会话存储
    if hasattr(session_store, "close"):
        await session_store.close()

    logger.info("服务已关闭")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""
    app = FastAPI(
        title="钉钉智能对话机器人",
        description=(
            "基于 FastAPI + Claude API 的钉钉企业内部智能对话机器人。"
            "支持 Stream 模式长连接接收消息。"
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # 注册路由
    app.include_router(health_router)
    app.include_router(webhook_router)
    app.include_router(admin_router)

    return app


app = create_app()
