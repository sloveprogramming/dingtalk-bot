"""LLM 对话插件 —— 主要智能对话处理插件。

作为兜底插件（fallback），处理所有未被其他插件处理的消息。
"""

from __future__ import annotations

from app.core.llm.base import LLMMessage
from app.core.message.plugins.base import BasePlugin, PluginContext
from app.models.message import IncomingMessage, OutgoingMessage
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMChatPlugin(BasePlugin):
    """LLM 对话插件：将用户消息发给 LLM 获取回复。

    作为兜底插件（register 时放到最后），处理所有未被其他插件处理的消息。
    """

    name = "llm_chat"
    description = "智能对话 —— 与 AI 助手聊天（兜底处理器）"

    async def can_handle(self, message: IncomingMessage) -> bool:
        # 兜底插件：始终可以处理
        return True

    async def handle(
        self,
        message: IncomingMessage,
        context: PluginContext,
    ) -> OutgoingMessage | None:
        if context.llm_provider is None:
            return OutgoingMessage.text(
                content="AI 服务暂未配置，请联系管理员。",
                target_users=[message.sender_id],
                conversation_id=message.conversation_id,
            )

        if not message.text.strip():
            return None

        session_mgr = context.session_manager
        if session_mgr is None:
            # 无会话管理时直接调用 LLM
            return await self._direct_chat(message, context)

        # 有会话管理时保留上下文
        return await self._context_chat(message, context)

    async def _direct_chat(
        self,
        message: IncomingMessage,
        context: PluginContext,
    ) -> OutgoingMessage:
        """无会话管理时直接调用 LLM。"""
        try:
            response = await context.llm_provider.chat(
                messages=[LLMMessage(role="user", content=message.text)],
                system=context.settings.llm.system_prompt if context.settings else None,
            )
        except Exception as exc:
            logger.error("LLM 调用失败: %s", exc)
            return OutgoingMessage.text(
                content="抱歉，AI 回复出了点问题，请稍后再试。",
                target_users=[message.sender_id],
                conversation_id=message.conversation_id,
            )

        return OutgoingMessage.text(
            content=response.content,
            target_users=[message.sender_id],
            conversation_id=message.conversation_id,
        )

    async def _context_chat(
        self,
        message: IncomingMessage,
        context: PluginContext,
    ) -> OutgoingMessage:
        """带上下文管理的 LLM 对话。"""
        session_mgr = context.session_manager
        conversation_id = message.conversation_id

        try:
            # 1. 获取/创建会话
            session = await session_mgr.get_or_create(
                conversation_id=conversation_id,
                user_id=message.sender_id,
                conversation_type=message.conversation_type,
                user_nick=message.sender_nick,
            )

            # 2. 估算用户消息 Token 数
            input_tokens = context.llm_provider.count_tokens(message.text)

            # 3. 保存用户消息
            await session_mgr.add_message(
                session_id=conversation_id,
                role="user",
                content=message.text,
                token_count=input_tokens,
            )

            # 4. 获取裁剪后的上下文
            history = await session_mgr.get_context(conversation_id)

            # 5. 转换为 LLM 消息格式
            llm_messages = [
                LLMMessage(role=entry.role, content=entry.content)
                for entry in history
                if entry.role in ("user", "assistant")
            ]

            # 6. 调用 LLM
            system_prompt = (
                context.settings.llm.system_prompt
                if context.settings
                else None
            )
            response = await context.llm_provider.chat(
                messages=llm_messages,
                system=system_prompt,
            )

            # 7. 保存助手回复
            await session_mgr.add_message(
                session_id=conversation_id,
                role="assistant",
                content=response.content,
                token_count=response.output_tokens,
            )

            return OutgoingMessage.text(
                content=response.content,
                target_users=[message.sender_id],
                conversation_id=conversation_id,
            )

        except Exception as exc:
            logger.error("LLM 对话处理失败: %s", exc)
            return OutgoingMessage.text(
                content="抱歉，AI 回复出了点问题，请稍后再试。",
                target_users=[message.sender_id],
                conversation_id=message.conversation_id,
            )
