"""钉钉 OpenAPI 异步客户端。

提供 Token 自动管理、消息发送、用户信息查询等功能。
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.core.dingtalk.constants import (
    MESSAGE_SEND_URL,
    TOKEN_URL,
    USER_GET_URL,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DingTalkClientError(Exception):
    """钉钉 API 调用错误。"""


class DingTalkClient:
    """钉钉 OpenAPI 异步客户端。

    用法:
        client = DingTalkClient(app_key="xxx", app_secret="yyy")
        await client.send_text(users=["user123"], content="你好", conversation_id="cid")
    """

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        bot_code: str = "",
        timeout: float = 10.0,
    ) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._bot_code = bot_code
        self._http_client = httpx.AsyncClient(timeout=timeout)

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = None  # asyncio.Lock 惰性初始化

    async def close(self) -> None:
        """关闭 HTTP 客户端，释放资源。"""
        await self._http_client.aclose()

    # ── Token 管理 ────────────────────────────────────────

    async def get_access_token(self) -> str:
        """获取有效的 access_token（自动刷新）。"""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        # 惰性初始化锁（避免在 __init__ 中使用 async）
        if self._token_lock is None:
            from asyncio import Lock

            self._token_lock = Lock()

        async with self._token_lock:
            # 双重检查 —— 拿到锁后重新检查 token 是否已刷新
            if self._access_token and time.time() < self._token_expires_at:
                return self._access_token
            return await self._refresh_token()

    async def _refresh_token(self) -> str:
        """调用钉钉 API 刷新 access_token。

        Returns:
            新的 access_token。

        Raises:
            DingTalkClientError: 刷新失败时抛出。
        """
        params = {"appkey": self._app_key, "appsecret": self._app_secret}
        try:
            response = await self._http_client.get(TOKEN_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise DingTalkClientError(
                f"Token 刷新 HTTP 错误: {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise DingTalkClientError(f"Token 刷新失败: {exc}") from exc

        if data.get("errcode") != 0:
            raise DingTalkClientError(
                f"Token 刷新 API 错误: {data.get('errcode')} - {data.get('errmsg')}"
            )

        self._access_token = data["access_token"]
        # 提前 60 秒过期，留出缓冲
        expires_in = data.get("expires_in", 7200) - 60
        self._token_expires_at = time.time() + expires_in

        logger.info("DingTalk access_token 已刷新，有效期 %ds", expires_in)
        return self._access_token

    # ── 消息发送 ──────────────────────────────────────────

    async def send_text(
        self,
        users: list[str],
        content: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """发送文本消息。

        Args:
            users: 接收消息的用户 UserId 列表。
            content: 消息文本内容。
            conversation_id: 会话 ID（群聊场景推荐传入）。

        Returns:
            钉钉 API 响应 JSON。

        Raises:
            DingTalkClientError: 发送失败时抛出。
        """
        payload = self._build_message_payload(
            msgtype="text",
            msg_content={"content": content},
            users=users,
            conversation_id=conversation_id,
        )
        return await self._post_message(payload)

    async def send_markdown(
        self,
        users: list[str],
        title: str,
        text: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """发送 Markdown 消息。

        Args:
            users: 接收消息的用户 UserId 列表。
            title: 消息标题（在钉钉通知中显示）。
            text: Markdown 格式的消息内容。
            conversation_id: 会话 ID。

        Returns:
            钉钉 API 响应 JSON。
        """
        payload = self._build_message_payload(
            msgtype="markdown",
            msg_content={"title": title, "text": text},
            users=users,
            conversation_id=conversation_id,
        )
        return await self._post_message(payload)

    async def send_action_card(
        self,
        users: list[str],
        title: str,
        text: str,
        btn_orientation: str = "1",
        single_title: str | None = None,
        single_url: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """发送交互式卡片消息。

        Args:
            users: 接收消息的用户 UserId 列表。
            title: 卡片标题。
            text: 卡片正文（支持 Markdown）。
            btn_orientation: 按钮排列方向，0=竖直，1=横向。
            single_title: 单个按钮标题（跳转链接模式）。
            single_url: 单个按钮链接。
            conversation_id: 会话 ID。

        Returns:
            钉钉 API 响应 JSON。
        """
        card_content: dict[str, Any] = {
            "title": title,
            "text": text,
            "btn_orientation": btn_orientation,
        }
        if single_title and single_url:
            card_content["single_title"] = single_title
            card_content["single_url"] = single_url

        payload = self._build_message_payload(
            msgtype="action_card",
            msg_content=card_content,
            users=users,
            conversation_id=conversation_id,
        )
        return await self._post_message(payload)

    # ── 用户信息 ──────────────────────────────────────────

    async def get_user_info(self, user_id: str) -> dict[str, Any]:
        """获取用户信息。

        Args:
            user_id: 用户 UserId。

        Returns:
            用户信息字典，包含 name、avatar 等字段。
        """
        token = await self.get_access_token()
        params = {"access_token": token, "userid": user_id}
        try:
            response = await self._http_client.get(USER_GET_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise DingTalkClientError(
                f"获取用户信息 HTTP 错误: {exc.response.status_code}"
            ) from exc

        if data.get("errcode") != 0:
            raise DingTalkClientError(
                f"获取用户信息 API 错误: {data.get('errcode')} - {data.get('errmsg')}"
            )
        return data

    # ── 内部方法 ──────────────────────────────────────────

    def _build_message_payload(
        self,
        msgtype: str,
        msg_content: dict[str, Any],
        users: list[str],
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """构建消息发送请求体。

        Args:
            msgtype: 消息类型。
            msg_content: 消息内容字典。
            users: 用户列表。
            conversation_id: 会话 ID。

        Returns:
            完整的请求体字典。
        """
        payload: dict[str, Any] = {
            "msgtype": msgtype,
            msgtype: msg_content,
            "userid_list": ",".join(users),
        }
        if conversation_id:
            # chatId 格式用 chatid，cid 格式用 conversationid
            if conversation_id.startswith("chat"):
                payload["chatid"] = conversation_id
            else:
                payload["conversationid"] = conversation_id
        # 群消息添加 robotCode 使消息以机器人身份发送
        if self._bot_code and conversation_id:
            payload["robotCode"] = self._bot_code
        return payload

    async def _post_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """向钉钉发送消息（自动处理 token 刷新和重试）。

        Args:
            payload: 消息请求体。

        Returns:
            钉钉 API 响应。

        Raises:
            DingTalkClientError: 发送失败（重试后仍失败）时抛出。
        """
        token = await self.get_access_token()
        params = {"access_token": token}

        try:
            response = await self._http_client.post(
                MESSAGE_SEND_URL,
                params=params,
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise DingTalkClientError(f"消息发送超时: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            # 401 表示 Token 过期，强制刷新后重试一次
            if exc.response.status_code == 401:
                logger.info("Token 过期，正在刷新后重试消息发送")
                self._access_token = None
                self._token_expires_at = 0.0
                token = await self._refresh_token()
                params["access_token"] = token
                response = await self._http_client.post(
                    MESSAGE_SEND_URL,
                    params=params,
                    content=json.dumps(payload),
                )
                response.raise_for_status()
                data = response.json()
            else:
                raise DingTalkClientError(
                    f"消息发送 HTTP 错误: {exc.response.status_code}"
                ) from exc

        if data.get("errcode") != 0:
            raise DingTalkClientError(
                f"消息发送 API 错误: {data.get('errcode')} - {data.get('errmsg')}"
            )

        logger.debug(
            "消息发送成功 | type=%s | users=%s",
            payload.get("msgtype"),
            payload.get("userid_list"),
        )
        return data
