"""钉钉 API 客户端单元测试（使用 respx mock HTTP）。"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.core.dingtalk.client import DingTalkClient, DingTalkClientError
from app.core.dingtalk.constants import TOKEN_URL, MESSAGE_SEND_URL


@pytest.fixture
def client() -> DingTalkClient:
    """测试用 DingTalkClient 实例。"""
    return DingTalkClient(
        app_key="test_key",
        app_secret="test_secret",
        timeout=5.0,
    )


class TestDingTalkClient:
    """DingTalkClient 功能测试。"""

    @respx.mock
    async def test_get_access_token_success(self, client: DingTalkClient):
        """成功获取 access_token。"""
        respx.get(TOKEN_URL).respond(
            json={"errcode": 0, "errmsg": "ok", "access_token": "abc123", "expires_in": 7200}
        )
        token = await client.get_access_token()
        assert token == "abc123"

    @respx.mock
    async def test_get_access_token_api_error(self, client: DingTalkClient):
        """获取 token 时 API 返回错误。"""
        respx.get(TOKEN_URL).respond(
            json={"errcode": 40001, "errmsg": "invalid credential"}
        )
        with pytest.raises(DingTalkClientError, match="API 错误"):
            await client.get_access_token()

    @respx.mock
    async def test_get_access_token_http_error(self, client: DingTalkClient):
        """获取 token 时 HTTP 请求失败。"""
        respx.get(TOKEN_URL).respond(status_code=500)
        with pytest.raises(DingTalkClientError, match="HTTP 错误"):
            await client.get_access_token()

    @respx.mock
    async def test_send_text_success(self, client: DingTalkClient):
        """成功发送文本消息。"""
        # Mock token
        respx.get(TOKEN_URL).respond(
            json={"errcode": 0, "errmsg": "ok", "access_token": "abc123", "expires_in": 7200}
        )
        # Mock 消息发送
        respx.post(MESSAGE_SEND_URL).respond(
            json={"errcode": 0, "errmsg": "ok", "messageId": "msg123", "taskId": "task123"}
        )
        result = await client.send_text(
            users=["user1", "user2"],
            content="测试消息",
            conversation_id="cid123",
        )
        assert result["errcode"] == 0
        assert result["messageId"] == "msg123"

    @respx.mock
    async def test_send_markdown_success(self, client: DingTalkClient):
        """成功发送 Markdown 消息。"""
        respx.get(TOKEN_URL).respond(
            json={"errcode": 0, "errmsg": "ok", "access_token": "abc123", "expires_in": 7200}
        )
        respx.post(MESSAGE_SEND_URL).respond(
            json={"errcode": 0, "errmsg": "ok", "messageId": "msg456"}
        )
        result = await client.send_markdown(
            users=["user1"],
            title="测试标题",
            text="# Markdown 内容",
            conversation_id="cid456",
        )
        assert result["errcode"] == 0

    @respx.mock
    async def test_send_message_auto_retry_on_401(self, client: DingTalkClient):
        """401 Token 过期后应自动刷新重试。"""
        # Mock token 获取
        respx.get(TOKEN_URL).respond(
            json={"errcode": 0, "errmsg": "ok", "access_token": "abc123", "expires_in": 7200}
        )
        # 第一次返回 401，第二次成功
        mock_post = respx.post(MESSAGE_SEND_URL)
        mock_post.side_effect = [
            Response(401, json={"errcode": 40014, "errmsg": "token expired"}),
            Response(200, json={"errcode": 0, "errmsg": "ok", "messageId": "msg789"}),
        ]
        result = await client.send_text(
            users=["user1"],
            content="重试测试",
        )
        assert result["errcode"] == 0
        assert result["messageId"] == "msg789"
        # 应发送了 2 次请求
        assert mock_post.call_count == 2

    @respx.mock
    async def test_send_message_api_error(self, client: DingTalkClient):
        """消息发送 API 返回错误。"""
        respx.get(TOKEN_URL).respond(
            json={"errcode": 0, "errmsg": "ok", "access_token": "abc123", "expires_in": 7200}
        )
        respx.post(MESSAGE_SEND_URL).respond(
            json={"errcode": 90001, "errmsg": "permission denied"}
        )
        with pytest.raises(DingTalkClientError, match="API 错误"):
            await client.send_text(users=["user1"], content="测试")

    @respx.mock
    async def test_close(self, client: DingTalkClient):
        """关闭客户端不应抛出异常。"""
        await client.close()

    @respx.mock
    async def test_get_user_info(self, client: DingTalkClient):
        """获取用户信息成功。"""
        respx.get(TOKEN_URL).respond(
            json={"errcode": 0, "errmsg": "ok", "access_token": "abc123", "expires_in": 7200}
        )
        respx.get(
            "https://oapi.dingtalk.com/user/get",
            params={"access_token": "abc123", "userid": "user123"},
        ).respond(
            json={
                "errcode": 0,
                "errmsg": "ok",
                "userid": "user123",
                "name": "张三",
                "avatar": "https://example.com/avatar.png",
            }
        )
        result = await client.get_user_info("user123")
        assert result["name"] == "张三"
        assert result["userid"] == "user123"
