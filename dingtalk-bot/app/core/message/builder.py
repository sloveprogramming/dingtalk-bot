"""消息响应构建器。

将内部 OutgoingMessage 转换为钉钉 API 所需的请求体格式。
"""

from __future__ import annotations

from typing import Any

from app.models.message import OutgoingMessage


def build_send_payload(msg: OutgoingMessage) -> dict[str, Any]:
    """将 OutgoingMessage 构建为钉钉消息发送 API 的请求体。

    Args:
        msg: 内部出站消息。

    Returns:
        符合钉钉 API 格式的请求体字典。
    """
    payload: dict[str, Any] = {
        "msgtype": msg.msg_type,
        msg.msg_type: msg.content,
    }

    if msg.target_users:
        payload["userid_list"] = ",".join(msg.target_users)

    if msg.conversation_id:
        payload["conversationid"] = msg.conversation_id

    return payload
