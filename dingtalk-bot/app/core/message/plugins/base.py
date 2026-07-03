"""插件抽象基类。

所有消息处理插件需继承 BasePlugin 并实现 can_handle 和 handle 方法。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from app.models.message import IncomingMessage, OutgoingMessage


@dataclass
class PluginContext:
    """插件执行上下文。"""

    session_manager: Any = None
    """会话管理器。"""

    dingtalk_client: Any = None
    """钉钉 API 客户端。"""

    llm_provider: Any = None
    """LLM 提供者。"""

    settings: Any = None
    """应用配置。"""


@dataclass
class PluginInfo:
    """插件元信息。"""

    name: str
    description: str


class BasePlugin(abc.ABC):
    """消息处理插件基类。"""

    name: str = "base"
    description: str = "插件基类"

    @abc.abstractmethod
    async def can_handle(self, message: IncomingMessage) -> bool:
        """判断该插件是否能处理此消息。

        Args:
            message: 入站消息。

        Returns:
            能否处理。
        """

    @abc.abstractmethod
    async def handle(
        self,
        message: IncomingMessage,
        context: PluginContext,
    ) -> OutgoingMessage | None:
        """处理消息并返回响应。

        Args:
            message: 入站消息。
            context: 插件上下文（会话管理器、LLM 提供者等）。

        Returns:
            出站消息（若需回复），或 None（不回复）。
        """

    def info(self) -> PluginInfo:
        """获取插件元信息。"""
        return PluginInfo(name=self.name, description=self.description)
