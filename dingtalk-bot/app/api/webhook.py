"""钉钉机器人回调端点 —— Stream 长连接模式。

Stream 模式下消息由钉钉服务器直接推送，无需签名验证和加解密。
消息接收后异步分发到插件链处理，不阻塞 HTTP 响应。
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.dingtalk.client import DingTalkClient
from app.core.message.handler import MessageHandler
from app.core.message.parser import parse_callback_message
from app.core.message.plugins.register import PluginRegistry
from app.core.session.manager import SessionManager
from app.dependencies import (
    get_dingtalk_client,
    get_llm_provider,
    get_plugin_registry,
    get_session_manager,
    get_settings,
)
from app.core.llm.base import LLMProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/callback")
async def dingtalk_callback(
    payload: dict[str, Any],
    request: Request,
    settings: Any = Depends(get_settings),
):
    """接收钉钉 Stream 模式推送的消息。

    流程:
        1. 异步后台处理消息（fire-and-forget）
        2. 立即返回成功响应
    """
    # 检查是否为 URL 验证事件（首次配置时）
    if payload.get("MsgType") == "check_url":
        logger.info("URL 验证成功，回调配置可用")
        return JSONResponse(status_code=200, content={"success": True})

    # 异步分发处理（fire-and-forget —— 不阻塞 HTTP 响应）
    msg = parse_callback_message(payload)
    asyncio.create_task(_dispatch_message_async(request, msg, payload))

    # 立即返回成功响应
    return JSONResponse(status_code=200, content={"success": True})


async def _dispatch_message_async(
    request: Request,
    msg: Any,
    raw_payload: dict | None = None,
) -> None:
    """在后台异步处理消息。

    通过依赖注入获取所有组件并分发给 MessageHandler。

    Args:
        request: FastAPI 请求对象（用于访问 app.state）。
        msg: 标准化的 IncomingMessage。
        raw_payload: 原始回调载荷（可选）。
    """
    try:
        settings = request.app.state.settings
        dingtalk_client: DingTalkClient | None = getattr(
            request.app.state, "dingtalk_client", None
        )
        session_manager: SessionManager | None = getattr(
            request.app.state, "session_manager", None
        )
        llm_provider: LLMProvider | None = getattr(
            request.app.state, "llm_provider", None
        )
        registry: PluginRegistry | None = getattr(
            request.app.state, "plugin_registry", None
        )

        if registry is None:
            logger.error("插件注册器未初始化，无法处理消息")
            return

        handler = MessageHandler(
            registry=registry,
            dingtalk_client=dingtalk_client,
            session_manager=session_manager,
            llm_provider=llm_provider,
            settings=settings,
        )

        await handler.handle_incoming(msg, raw_payload)

    except Exception as exc:
        logger.error("后台消息处理异常: %s", exc, exc_info=True)