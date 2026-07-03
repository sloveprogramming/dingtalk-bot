"""钉钉 Stream 模式客户端。"""

from __future__ import annotations

import asyncio
import re

import dingtalk_stream
from dingtalk_stream import AckMessage
from dingtalk_stream.chatbot import ChatbotMessage

from app.candidate_store import CandidateStore
from app.core.message.handler import MessageHandler
from app.utils.logger import get_logger

logger = get_logger(__name__)

# 存储群聊的 sessionWebhook（按 conversationId 索引）
# 事件处理器通过这个 dict 获取 webhook 来发送主动消息
group_webhooks: dict[str, str] = {}

# 关键词：表示已完成的回复
COMPLETION_PATTERNS = [
    r"已完成",
    r"做完了",
    r"做好了",
    r"全部完成",
    r"都做完了",
    r"做完了",
    r"complete",
    r"done",
    r"finish",
]


class DingTalkStreamBot:
    """钉钉 Stream 模式机器人。"""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        message_handler: MessageHandler | None = None,
        event_handler: dingtalk_stream.EventHandler | None = None,
        authorized_users: list[str] | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._message_handler = message_handler
        self._event_handler = event_handler
        self._authorized_users = authorized_users or []
        self._client: dingtalk_stream.DingTalkStreamClient | None = None
        self._running = False
        self._store = CandidateStore()

    def _build_handler(self):
        handler = self._message_handler
        store = self._store
        authorized_users = self._authorized_users

        class BotHandler(dingtalk_stream.ChatbotHandler):
            async def process(self, callback: dingtalk_stream.CallbackMessage):
                try:
                    data = callback.data if hasattr(callback, "data") else {}
                    if not data:
                        return (AckMessage.STATUS_BAD_REQUEST, "bad request")

                    logger.info("收到消息: %s", str(data)[:500])

                    incoming_msg = ChatbotMessage()
                    incoming_msg.sender_staff_id = data.get("senderStaffId", "")
                    incoming_msg.session_webhook = data.get("sessionWebhook", "")
                    incoming_msg.sender_id = data.get("senderId", "")

                    # 存储 sessionWebhook，用于事件处理时发送主动消息
                    sw = data.get("sessionWebhook", "")
                    cid = data.get("conversationId", "")
                    if sw and cid:
                        group_webhooks[cid] = sw
                    incoming_msg.sender_nick = data.get("senderNick", "")
                    incoming_msg.conversation_id = data.get("conversationId", "")
                    incoming_msg.conversation_title = data.get("conversationTitle", "")

                    text_content = ""
                    text_raw = data.get("text", {})
                    if isinstance(text_raw, dict):
                        text_content = text_raw.get("content", "") or text_raw.get("text", "")
                    elif isinstance(text_raw, str):
                        text_content = text_raw

                    text_content = text_content.strip()
                    if not text_content:
                        return (AckMessage.STATUS_OK, "ok")

                    # senderStaffId 是用户的企业内部 ID，用于权限判断
                    user_id = incoming_msg.sender_staff_id or incoming_msg.sender_id
                    group_id = incoming_msg.conversation_id
                    text_lower = text_content.lower()

                    # 更新候选人信息（从 senderNick 获取真实姓名）
                    sender_nick = incoming_msg.sender_nick or ""
                    if group_id and sender_nick:
                        store.update_candidate_info(group_id, sender_nick)

                    # ── 检查是否请求状态查询 ──
                    if re.search(r"/status|状态|进度|完成情况", text_lower):
                        if user_id in authorized_users:
                            status_text = _build_status_text(store, group_id)
                        else:
                            status_text = "⚠️ 抱歉，只有 HR 和管理员才能查看候选人状态。"
                        try:
                            self.reply_text(status_text, incoming_msg)
                        except Exception as e:
                            logger.error("发送状态失败: %s", e)
                        return (AckMessage.STATUS_OK, "ok")

                    # ── 检查是否回复了"已完成" ──
                    is_complete = any(
                        re.search(p, text_lower) for p in COMPLETION_PATTERNS
                    )
                    if is_complete and group_id:
                        name = incoming_msg.sender_nick or ""
                        updated = store.mark_completed(group_id, user_name=name)
                        if updated:
                            reply = "好的，稍等我这边会通知HR审核你的测试，稍后会联系您！"
                        else:
                            reply = "未找到您的记录，请联系 HR 确认。"
                        try:
                            self.reply_text(reply, incoming_msg)
                        except Exception as e:
                            logger.error("发送完成确认失败: %s", e)
                        return (AckMessage.STATUS_OK, "ok")

                    # ── 其他对话 → AI 回复 ──
                    if handler:
                        try:
                            self.reply_text("🤔 正在思考中，请稍等...", incoming_msg)
                            response = await handler.get_llm_response(
                                user_id=user_id,
                                user_nick=incoming_msg.sender_nick,
                                conversation_id=group_id,
                                text=text_content,
                            )
                            self.reply_text(response, incoming_msg)
                        except Exception as e:
                            logger.error("AI 回复失败: %s", e)
                            try:
                                self.reply_text("抱歉，我现在无法回复，请稍后再试。", incoming_msg)
                            except Exception:
                                pass
                    else:
                        try:
                            self.reply_text("你好！有什么可以帮助你的？", incoming_msg)
                        except Exception:
                            pass

                except Exception as e:
                    logger.error("消息处理异常: %s", e, exc_info=True)

                return (AckMessage.STATUS_OK, "ok")

        return BotHandler

    async def start(self) -> None:
        if self._running:
            return
        self._running = True

        credential = dingtalk_stream.Credential(self._client_id, self._client_secret)
        self._client = dingtalk_stream.DingTalkStreamClient(credential)

        BotHandlerClass = self._build_handler()
        logger.info("正在注册消息处理器...")
        self._client.register_callback_handler(ChatbotMessage.TOPIC, BotHandlerClass())

        logger.info("Stream 客户端连接中...")
        try:
            if self._event_handler:
                logger.info("正在注册群聊事件处理器...")
                self._client.register_all_event_handler(self._event_handler)
                logger.info("群聊事件监听器已注册")

            await self._client.start()
        except asyncio.CancelledError:
            logger.info("Stream 已取消")
        except Exception as exc:
            logger.error("Stream 连接失败: %s", exc, exc_info=True)
            self._running = False

    async def stop(self) -> None:
        if self._client and self._running:
            self._running = False
            await self._client.close()
            logger.info("Stream 已停止")


def _build_status_text(store: CandidateStore, group_id: str) -> str:
    candidates = store.get_all_candidates()
    if not candidates:
        return "暂无候选人记录。"

    lines = ["**候选人完成状态**\n"]
    for i, c in enumerate(candidates, 1):
        name = c.get("user_name") or f"候选人{i}"
        status = c.get("status", "pending")
        joined = c.get("joined_at", "")[:10] if c.get("joined_at") else ""

        if status == "completed":
            done_at = c.get("completed_at", "")[:10] if c.get("completed_at") else ""
            lines.append(f"{i}. {name}  **完成** ({done_at})")
        else:
            lines.append(f"{i}. {name}  **未完成** (入群{joined})")

    lines.append("\n@我并回复「已完成」即可更新状态")
    return "\n".join(lines)
