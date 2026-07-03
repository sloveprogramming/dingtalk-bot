"""会话数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MessageEntry:
    """会话中的一条消息记录。"""

    role: str
    """角色: user | assistant | system。"""

    content: str
    """消息内容。"""

    timestamp: datetime = field(default_factory=datetime.now)
    """消息时间戳。"""

    token_count: int = 0
    """该消息的 Token 估算数。"""


@dataclass
class Session:
    """一次对话会话。"""

    session_id: str
    """会话唯一标识（通常是 conversation_id）。"""

    conversation_type: str
    """会话类型: 1=单聊, 2=群聊。"""

    user_id: str
    """用户 UserId。"""

    user_nick: str = ""
    """用户昵称。"""

    history: list[MessageEntry] = field(default_factory=list)
    """消息历史记录。"""

    created_at: datetime = field(default_factory=datetime.now)
    """会话创建时间。"""

    updated_at: datetime = field(default_factory=datetime.now)
    """最后更新时间。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """附加元数据。"""

    @property
    def total_tokens(self) -> int:
        """会话累计 Token 数。"""
        return sum(msg.token_count for msg in self.history)

    @property
    def message_count(self) -> int:
        """消息总数。"""
        return len(self.history)

    def add_message(self, role: str, content: str, token_count: int = 0) -> None:
        """添加一条消息到历史。

        Args:
            role: user / assistant / system。
            content: 消息内容。
            token_count: 估算 Token 数。
        """
        self.history.append(
            MessageEntry(role=role, content=content, token_count=token_count)
        )
        self.updated_at = datetime.now()
