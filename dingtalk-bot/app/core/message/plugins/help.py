"""帮助插件 —— 列出所有可用插件及说明。"""

from __future__ import annotations

from app.core.message.plugins.base import BasePlugin, PluginContext
from app.models.message import IncomingMessage, OutgoingMessage


class HelpPlugin(BasePlugin):
    """帮助插件：显示所有可用命令列表。"""

    name = "help"
    description = "显示帮助信息 —— 列出所有可用命令"

    async def can_handle(self, message: IncomingMessage) -> bool:
        text = message.text.strip()
        return text in ("/help", "/start", "帮助", "帮助")

    async def handle(
        self,
        message: IncomingMessage,
        context: PluginContext,
    ) -> OutgoingMessage | None:
        # 从上下文中获取已注册的插件列表
        registry = getattr(context, "plugin_registry", None)
        if registry is None:
            plugins_text = "暂无可用的插件列表。"
        else:
            plugins = registry.list_plugins()
            lines = ["**可用命令：**\n"]
            for p in plugins:
                lines.append(f"- `{p.name}` — {p.description}")
            plugins_text = "\n".join(lines) if lines else "暂无可用的命令。"

        return OutgoingMessage.markdown(
            title="🤖 帮助中心",
            text=plugins_text,
            target_users=[message.sender_id],
            conversation_id=message.conversation_id,
        )
