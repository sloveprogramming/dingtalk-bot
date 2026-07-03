"""调试插件 —— 回显用户消息。"""

from __future__ import annotations

from app.core.message.plugins.base import BasePlugin, PluginContext
from app.models.message import IncomingMessage, OutgoingMessage


class EchoPlugin(BasePlugin):
    """回显插件：将用户消息原样返回。"""

    name = "echo"
    description = "调试回显 —— 将用户消息原样返回"

    async def can_handle(self, message: IncomingMessage) -> bool:
        return message.text.startswith("/echo")

    async def handle(
        self,
        message: IncomingMessage,
        context: PluginContext,
    ) -> OutgoingMessage | None:
        content = message.text.replace("/echo", "").strip()
        if not content:
            content = f"收到消息: {message.text}"

        return OutgoingMessage.text(
            content=content,
            target_users=[message.sender_id],
            conversation_id=message.conversation_id,
        )
