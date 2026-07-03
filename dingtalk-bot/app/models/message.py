"""内部消息模型 —— 统一的消息表示，与钉钉协议解耦。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class IncomingMessage:
    """标准化后的入站消息。

    由 MessageParser 将钉钉回调 JSON 转换为该类型。
    """

    msg_id: str
    """消息 ID（用于去重）。"""

    conversation_id: str
    """会话 ID。"""

    conversation_type: str
    """会话类型: 1=单聊, 2=群聊。"""

    sender_id: str
    """发送者 UserId。"""

    sender_nick: str = ""
    """发送者昵称。"""

    sender_staff_id: str = ""
    """发送者企业内部 StaffId。"""

    bot_user_id: str = ""
    """机器人自身的 UserId。"""

    msg_type: str = ""
    """消息类型: text / picture / voice / link。"""

    text: str = ""
    """文本内容（文本消息时有效）。"""

    raw_content: dict[str, Any] = field(default_factory=dict)
    """原始消息内容字典。"""

    created_at: datetime | None = None
    """消息创建时间。"""


@dataclass
class OutgoingMessage:
    """出站消息（待发送）。"""

    msg_type: str
    """消息类型: text / markdown / action_card。"""

    content: dict[str, Any]
    """消息内容（格式取决于 msg_type）。"""

    target_users: list[str] | None = None
    """目标用户 UserId 列表。"""

    conversation_id: str | None = None
    """目标会话 ID。"""

    @classmethod
    def text(cls, content: str, **kwargs) -> OutgoingMessage:
        """快速创建文本消息。"""
        return cls(msg_type="text", content={"content": content}, **kwargs)

    @classmethod
    def markdown(cls, title: str, text: str, **kwargs) -> OutgoingMessage:
        """快速创建 Markdown 消息。"""
        return cls(
            msg_type="markdown",
            content={"title": title, "text": text},
            **kwargs,
        )
