class CallbackMessage(BaseModel):
    """解密后的回调消息体。"""

    conversation_id: str = Field(alias="ConversationId")
    """会话 ID。"""

    conversation_type: str = Field(alias="ConversationType")
    """会话类型：1=单聊，2=群聊。"""

    sender_id: str = Field(alias="SenderId")
    """发送者 UserId。"""

    sender_nick: str = Field(alias="SenderNick", default="")
    """发送者昵称。"""

    sender_staff_id: str = Field(alias="SenderStaffId", default="")
    """发送者 StaffId（企业内部）。"""

    chatbot_user_id: str = Field(alias="ChatbotUserId", default="")
    """机器人 UserId（可用于回复）。"""

    msg_id: str = Field(alias="MsgId")
    """消息 ID（可用于去重）。"""

    msg_type: str = Field(alias="MsgType")
    """消息类型：text / picture / voice / link 等。"""

    content: dict[str, Any] = Field(alias="Content", default_factory=dict)
    """消息内容字典（不同 MsgType 结构不同）。"""

    create_at_raw: int = Field(alias="CreateAt", default=0)
    """消息创建时间戳（毫秒）。"""

    @property
    def create_at(self) -> datetime:
        return datetime.fromtimestamp(self.create_at_raw / 1000)

    @property
    def text_content(self) -> str:
        """获取文本消息内容（仅对 text 类型有效）。"""
        return self.content.get("content", "") if self.content else ""


# ── Token 响应 ────────────────────────────────────────────


class TokenResponse(BaseModel):
    """获取 access_token 的 API 响应。"""

    errcode: int = 0
    errmsg: str = "ok"
    access_token: str = ""
    expires_in: int = 7200


# ── 消息发送响应 ──────────────────────────────────────────


class MessageSendResponse(BaseModel):
    """消息发送 API 响应。"""

    errcode: int = 0
    errmsg: str = "ok"
    message_id: str = Field(default="", alias="messageId")
    task_id: str = Field(default="", alias="taskId")
