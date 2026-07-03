"""钉钉群聊事件监听器。

监听群成员加入事件，发送欢迎语+测试链接，记录候选人。
"""

from __future__ import annotations

from typing import Any

import dingtalk_stream
from dingtalk_stream import AckMessage

from app.candidate_store import CandidateStore
from app.core.dingtalk.client import DingTalkClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

EVENT_GROUP_MEMBER_ADD = "chat_add_member"
EVENT_GROUP_MEMBER_REMOVE = "chat_remove_member"


class GroupEventHandler(dingtalk_stream.EventHandler):
    """群聊事件处理器。"""

    def __init__(self, dingtalk_client: DingTalkClient | None = None):
        super().__init__()
        self._dingtalk_client = dingtalk_client
        self._store = CandidateStore()

    async def process(self, event: dingtalk_stream.EventMessage):
        # 记录所有收到的事件，方便排查
        event_type = event.headers.event_type if hasattr(event.headers, "event_type") else ""
        if not event_type:
            event_type = event.data.get("eventType", "")

        event_data_str = str(event.data)[:200] if event.data else "{}"
        logger.info("收到群事件: type=%s | data=%s", event_type, event_data_str)

        if event_type == EVENT_GROUP_MEMBER_ADD:
            await self._handle_member_add(event)
        elif event_type == EVENT_GROUP_MEMBER_REMOVE:
            await self._handle_member_remove(event)
        # 其他事件记录下来但不处理

        return (AckMessage.STATUS_OK, "ok")

    async def _handle_member_add(self, event: dingtalk_stream.EventMessage) -> None:
        data = event.data if isinstance(event.data, dict) else {}
        # 群事件使用 chatId 而非 conversationId
        conversation_id = data.get("chatId", "") or data.get("conversationId", "") or data.get("conversation_id", "")
        # 新成员列表（unionId 数组）
        members = data.get("unionId", [])

        for uid in members:
            if not uid:
                continue

            # 记录候选人（暂用 unionId，后续用户发消息时可关联到真实 userId）
            self._store.add_candidate(
                user_id=uid,
                user_name=uid,
                group_id=conversation_id,
            )

            # 发送欢迎语 + 链接
            name = data.get("userName", "") or "新同学"
            welcome = self._build_welcome(name)
            await self._send_group_message(conversation_id, welcome)

    async def _handle_member_remove(self, event: dingtalk_stream.EventMessage) -> None:
        data = event.data if isinstance(event.data, dict) else {}
        conversation_id = data.get("chatId", "") or data.get("conversationId", "") or data.get("conversation_id", "")
        if conversation_id:
            self._store.remove_candidate(conversation_id)

    def _build_welcome(self, name: str) -> str:
        """构建欢迎消息（含测试链接）。"""
        # ===== 在这里修改欢迎语和链接 =====
        return (
            f"🎉 欢迎 {name} 加入面试群！\n"
            f"我是新农哥，您的面试助手，请先将您的简历发到群里。\n"
            f"请完成以下测试内容，完成后 @ {self._dingtalk_client.bot_name} 并回复 **已完成**：\n\n"
            f"📝 新农哥候选人行为测试：https://www.qingsuyun.com/h5/250845/18081876029/\n"
            f"📋 人格测试(请打开微信复制这段链接)：#小程序://九型人格/JYXBOERJRrV7jAo\n\n"
            f"全部完成后请将完成后的“截图”发到群里并 @我 回复「已完成」，我会来联系您。"
        )

    async def _send_group_message(self, conversation_id: str, text: str) -> None:
        if not self._dingtalk_client or not conversation_id:
            logger.warning("无法发送群消息，缺少客户端或会话 ID")
            return

        try:
            await self._dingtalk_client.send_text(
                users=[],
                content=text,
                conversation_id=conversation_id,
            )
            logger.info("欢迎消息已发送 | group=%s", conversation_id)
        except Exception as exc:
            logger.error("欢迎消息发送失败: %s", exc)