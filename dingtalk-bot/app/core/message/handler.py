"""消息分发管道 —— 接收入站消息，路由到插件处理，发送响应。"""

from __future__ import annotations

from typing import Any

from app.core.message.plugins.base import PluginContext
from app.core.message.plugins.register import PluginRegistry
from app.models.message import IncomingMessage, OutgoingMessage
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MessageHandler:
    """消息处理器 —— 分发管道的核心。

    职责:
    1. 接收 IncomingMessage
    2. 遍历插件责任链，选择第一个 can_handle 返回 True 的插件
    3. 调用插件 handle 方法获取响应
    4. 通过 DingTalkClient 发送响应
    """

    def __init__(
        self,
        registry: PluginRegistry,
        dingtalk_client: Any = None,
        session_manager: Any = None,
        llm_provider: Any = None,
        settings: Any = None,
    ) -> None:
        self._registry = registry
        self._dingtalk_client = dingtalk_client
        self._session_manager = session_manager
        self._llm_provider = llm_provider
        self._settings = settings

    async def handle_incoming(
        self,
        message: IncomingMessage,
        raw_payload: dict | None = None,
    ) -> None:
        """处理一条入站消息。

        Args:
            message: 标准化后的入站消息。
            raw_payload: 原始回调载荷（用于调试/日志）。
        """
        # 1. 跳过非文本消息
        if message.msg_type not in ("text", ""):
            logger.debug("跳过非文本消息: type=%s", message.msg_type)
            return

        # 2. 查找匹配的插件
        plugin = await self._find_plugin(message)
        if plugin is None:
            logger.debug("无插件可处理消息: %s", message.msg_id)
            return

        logger.info(
            "插件命中: %s | msg=%s | sender=%s",
            plugin.name,
            message.msg_id,
            message.sender_id,
        )

        # 3. 构建上下文并执行插件
        context = PluginContext(
            session_manager=self._session_manager,
            dingtalk_client=self._dingtalk_client,
            llm_provider=self._llm_provider,
            settings=self._settings,
        )

        try:
            response = await plugin.handle(message, context)
        except Exception as exc:
            logger.error(
                "插件执行异常: %s | msg=%s | error=%s",
                plugin.name,
                message.msg_id,
                exc,
            )
            response = OutgoingMessage.text(
                content="抱歉，处理您的消息时出现错误，请稍后再试。",
                target_users=[message.sender_id],
                conversation_id=message.conversation_id,
            )

        # 4. 发送响应
        if response is not None:
            await self._send_response(response)

    async def _find_plugin(self, message: IncomingMessage):
        """遍历所有注册插件，找到第一个能处理该消息的。"""
        for plugin in self._registry._plugins.values():
            try:
                if await plugin.can_handle(message):
                    return plugin
            except Exception:
                continue
        return None

    async def _send_response(self, response: OutgoingMessage) -> None:
        """通过 DingTalk 客户端发送出站消息。"""
        if self._dingtalk_client is None:
            logger.warning("DingTalk 客户端未配置，跳过消息发送")
            return

        try:
            if response.msg_type == "text":
                await self._dingtalk_client.send_text(
                    users=response.target_users or [],
                    content=response.content.get("content", ""),
                    conversation_id=response.conversation_id,
                )
            elif response.msg_type == "markdown":
                await self._dingtalk_client.send_markdown(
                    users=response.target_users or [],
                    title=response.content.get("title", ""),
                    text=response.content.get("text", ""),
                    conversation_id=response.conversation_id,
                )
            else:
                logger.warning("不支持的消息类型: %s", response.msg_type)
        except Exception as exc:
            logger.error("消息发送失败: %s", exc)

    async def get_llm_response(
        self,
        user_id: str,
        user_nick: str,
        conversation_id: str,
        text: str,
    ) -> str:
        """获取 LLM 回复文本（不发送消息，供 Stream 模式使用）。

        Args:
            user_id: 用户 ID。
            user_nick: 用户昵称。
            conversation_id: 会话 ID。
            text: 用户消息文本。

        Returns:
            LLM 回复文本。
        """
        # 构造临时消息对象
        msg = IncomingMessage(
            msg_id="stream_" + conversation_id,
            conversation_id=conversation_id,
            conversation_type="1",
            sender_id=user_id,
            sender_nick=user_nick,
            msg_type="text",
            text=text,
        )

        # 查找匹配的插件
        plugin = await self._find_plugin(msg)
        if plugin is None:
            return "抱歉，我没有理解您的意思。"

        context = PluginContext(
            session_manager=self._session_manager,
            dingtalk_client=self._dingtalk_client,
            llm_provider=self._llm_provider,
            settings=self._settings,
        )

        try:
            response = await plugin.handle(msg, context)
        except Exception as exc:
            logger.error("LLM 响应获取失败: %s", exc)
            return "抱歉，AI 回复出了点问题，请稍后再试。"

        if response is None:
            return ""

        return response.content.get("content", "") or response.content.get("text", "")
