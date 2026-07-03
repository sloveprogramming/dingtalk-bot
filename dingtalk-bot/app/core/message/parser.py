"""钉钉回调消息解析器。

将钉钉开放平台推送的解密后 JSON 转换为内部统一的 IncomingMessage。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.models.message import IncomingMessage


def parse_callback_message(raw: dict[str, Any]) -> IncomingMessage:
    """将钉钉回调的原始字典解析为 IncomingMessage。

    Args:
        raw: 从 DingTalkCrypto.decrypt() 得到的字典。
              字段: ConversationId, MsgType, SenderId, Content 等。

    Returns:
        标准化后的 IncomingMessage 实例。

    Raises:
        ValueError: 缺少必要字段时抛出。
    """
    msg_type = raw.get("MsgType", "")

    # 解析 Content（不同消息类型结构不同）
    content_raw = raw.get("Content", {})
    if isinstance(content_raw, str):
        try:
            content_raw = json.loads(content_raw)
        except (json.JSONDecodeError, TypeError):
            content_raw = {"content": content_raw}

    # 提取文本内容
    text = _extract_text(msg_type, content_raw)

    # 解析时间戳
    created_at = None
    create_at_raw = raw.get("CreateAt")
    if create_at_raw:
        try:
            created_at = datetime.fromtimestamp(int(create_at_raw) / 1000)
        except (ValueError, TypeError):
            pass

    return IncomingMessage(
        msg_id=str(raw.get("MsgId", "")),
        conversation_id=str(raw.get("ConversationId", "")),
        conversation_type=str(raw.get("ConversationType", "")),
        sender_id=str(raw.get("SenderId", "")),
        sender_nick=str(raw.get("SenderNick", "")),
        sender_staff_id=str(raw.get("SenderStaffId", "")),
        bot_user_id=str(raw.get("ChatbotUserId", "")),
        msg_type=msg_type,
        text=text,
        raw_content=content_raw,
        created_at=created_at,
    )


def _extract_text(msg_type: str, content: dict[str, Any]) -> str:
    """从消息内容中提取纯文本。

    Args:
        msg_type: 消息类型。
        content: 消息内容字典。

    Returns:
        提取出的文本。
    """
    if msg_type == "text":
        return content.get("content", "")

    if msg_type in ("picture", "image"):
        return f"[图片] {content.get('downloadCode', '')}"

    if msg_type == "voice":
        return "[语音消息]"

    if msg_type == "link":
        text = content.get("text", "")
        title = content.get("title", "")
        url = content.get("url", "")
        return f"[链接] {title}: {text} ({url})"

    # 未知类型，尝试完整序列化
    return str(content)
