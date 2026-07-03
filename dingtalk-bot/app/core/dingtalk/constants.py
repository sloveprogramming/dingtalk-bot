"""钉钉开放平台常量定义。"""

from __future__ import annotations

from enum import StrEnum


# ── 开放平台 API 端点 ─────────────────────────────────────
BASE_URL = "https://oapi.dingtalk.com"

# Token
TOKEN_URL = f"{BASE_URL}/gettoken"

# 消息发送
MESSAGE_SEND_URL = f"{BASE_URL}/chat/send"
MESSAGE_SEND_TO_CONVERSATION_URL = f"{BASE_URL}/message/send"
MESSAGE_SEND_BY_TEMPLATE_URL = f"{BASE_URL}/message/send_by_template"  # 交互式卡片

# 用户管理
USER_GET_URL = f"{BASE_URL}/user/get"
USER_LIST_URL = f"{BASE_URL}/user/list"


# ── 消息类型 ──────────────────────────────────────────────
class MessageType(StrEnum):
    """钉钉消息类型枚举。"""

    TEXT = "text"
    MARKDOWN = "markdown"
    LINK = "link"
    ACTION_CARD = "action_card"      # 交互式卡片
    IMAGE = "image"
    VOICE = "voice"
    FILE = "file"
    OA = "oa"                        # OA 审批消息


# ── 回调事件类型 ──────────────────────────────────────────
class CallbackEventType(StrEnum):
    """钉钉回调事件类型。"""

    CHECK_URL = "check_url"               # URL 验证（首次配置回调）
    TEXT = "text"                          # 文本消息
    PICTURE = "picture"                    # 图片消息
    VOICE = "voice"                        # 语音消息
    LINK = "link"                          # 链接消息
    ACTION_CARD = "action_card_callback"   # 卡片回调


