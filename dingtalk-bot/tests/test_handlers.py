"""消息处理器与插件分发单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.message.handler import MessageHandler
from app.core.message.plugins.base import BasePlugin, PluginContext
from app.core.message.plugins.echo import EchoPlugin
from app.core.message.plugins.help import HelpPlugin
from app.core.message.plugins.llm_chat import LLMChatPlugin
from app.core.message.plugins.register import PluginRegistry
from app.models.message import IncomingMessage, OutgoingMessage


@pytest.fixture
def registry() -> PluginRegistry:
    return PluginRegistry()


@pytest.fixture
def mock_dingtalk() -> MagicMock:
    client = MagicMock()
    client.send_text = AsyncMock()
    client.send_markdown = AsyncMock()
    return client


@pytest.fixture
def mock_llm() -> MagicMock:
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=MagicMock(
        content="AI 回复",
        output_tokens=10,
    ))
    llm.count_tokens = MagicMock(return_value=10)
    return llm


def make_msg(text: str, msg_type: str = "text", msg_id: str = "msg1") -> IncomingMessage:
    return IncomingMessage(
        msg_id=msg_id,
        conversation_id="cid_test",
        conversation_type="1",
        sender_id="user1",
        sender_nick="测试用户",
        msg_type=msg_type,
        text=text,
    )


class TestPluginRegistry:
    """PluginRegistry 功能测试。"""

    def test_register_and_list(self, registry: PluginRegistry):
        registry.register(EchoPlugin())
        registry.register(HelpPlugin())
        plugins = registry.list_plugins()
        assert len(plugins) == 2
        names = [p.name for p in plugins]
        assert "echo" in names
        assert "help" in names

    def test_get_plugin(self, registry: PluginRegistry):
        registry.register(EchoPlugin())
        plugin = registry.get("echo")
        assert plugin is not None
        assert plugin.name == "echo"

    def test_get_nonexistent(self, registry: PluginRegistry):
        assert registry.get("nonexistent") is None


class TestEchoPlugin:
    """EchoPlugin 测试。"""

    @pytest.fixture
    def plugin(self) -> EchoPlugin:
        return EchoPlugin()

    async def test_can_handle_echo(self, plugin: EchoPlugin):
        assert await plugin.can_handle(make_msg("/echo 你好")) is True
        assert await plugin.can_handle(make_msg("/echo")) is True

    async def test_cannot_handle_normal(self, plugin: EchoPlugin):
        assert await plugin.can_handle(make_msg("你好")) is False

    async def test_handle_with_content(self, plugin: EchoPlugin):
        msg = make_msg("/echo 回复我")
        result = await plugin.handle(msg, PluginContext())
        assert result is not None
        assert "回复我" in result.content.get("content", "")
        assert result.target_users == ["user1"]

    async def test_handle_without_content(self, plugin: EchoPlugin):
        msg = make_msg("/echo")
        result = await plugin.handle(msg, PluginContext())
        assert result is not None
        assert "收到消息" in result.content.get("content", "")


class TestHelpPlugin:
    """HelpPlugin 测试。"""

    @pytest.fixture
    def plugin(self) -> HelpPlugin:
        return HelpPlugin()

    async def test_can_handle_help_commands(self, plugin: HelpPlugin):
        assert await plugin.can_handle(make_msg("/help")) is True
        assert await plugin.can_handle(make_msg("/start")) is True
        assert await plugin.can_handle(make_msg("帮助")) is True

    async def test_handle_no_registry(self, plugin: HelpPlugin):
        msg = make_msg("/help")
        result = await plugin.handle(msg, PluginContext())
        assert result is not None
        assert result.msg_type == "markdown"


class TestLLMChatPlugin:
    """LLMChatPlugin 测试。"""

    @pytest.fixture
    def plugin(self) -> LLMChatPlugin:
        return LLMChatPlugin()

    async def test_can_handle_always(self, plugin: LLMChatPlugin):
        assert await plugin.can_handle(make_msg("任意消息")) is True

    async def test_handle_no_llm(self, plugin: LLMChatPlugin):
        """没有 LLM 时应提示未配置。"""
        msg = make_msg("你好")
        result = await plugin.handle(msg, PluginContext())
        assert result is not None
        assert "暂未配置" in result.content.get("content", "")

    async def test_handle_with_llm(
        self, plugin: LLMChatPlugin, mock_llm: MagicMock
    ):
        """有 LLM 时应正确调用。"""
        msg = make_msg("你好")
        result = await plugin.handle(msg, PluginContext(llm_provider=mock_llm))
        assert result is not None
        assert result.target_users == ["user1"]
        mock_llm.chat.assert_awaited_once()

    async def test_handle_empty_text(self, plugin: LLMChatPlugin, mock_llm: MagicMock):
        """空文本应返回 None。"""
        msg = make_msg("")
        result = await plugin.handle(msg, PluginContext(llm_provider=mock_llm))
        assert result is None


class TestMessageHandler:
    """MessageHandler 分发逻辑测试。"""

    @pytest.fixture
    def handler(
        self, registry: PluginRegistry, mock_dingtalk: MagicMock
    ) -> MessageHandler:
        registry.register(EchoPlugin())
        registry.register(LLMChatPlugin())
        return MessageHandler(
            registry=registry,
            dingtalk_client=mock_dingtalk,
        )

    async def test_echo_plugin_selected_first(
        self, handler: MessageHandler, mock_dingtalk: MagicMock
    ):
        """/echo 消息应由 EchoPlugin 处理。"""
        msg = make_msg("/echo 测试回显")
        await handler.handle_incoming(msg)
        mock_dingtalk.send_text.assert_awaited_once()
        _, kwargs = mock_dingtalk.send_text.await_args
        assert "测试回显" in kwargs["content"]

    async def test_llm_chat_as_fallback(
        self, handler: MessageHandler, mock_dingtalk: MagicMock
    ):
        """普通消息应由 LLMChatPlugin 处理。"""
        msg = make_msg("你好")
        await handler.handle_incoming(msg)
        # LLM 未配置，应回复"暂未配置"
        mock_dingtalk.send_text.assert_awaited_once()
        _, kwargs = mock_dingtalk.send_text.await_args
        assert "暂未配置" in kwargs["content"]

    async def test_skip_non_text(
        self, handler: MessageHandler, mock_dingtalk: MagicMock
    ):
        """非文本消息应跳过。"""
        msg = make_msg("", msg_type="picture")
        await handler.handle_incoming(msg)
        mock_dingtalk.send_text.assert_not_called()

    async def test_handler_error_fallback(
        self, registry: PluginRegistry, mock_dingtalk: MagicMock
    ):
        """插件抛出异常时应发送友好的错误提示。"""
        class BrokenPlugin(BasePlugin):
            name = "broken"
            description = "总是抛出异常"

            async def can_handle(self, message) -> bool:
                return True

            async def handle(self, message, context) -> OutgoingMessage:
                raise RuntimeError("故意崩溃")

        registry.register(BrokenPlugin())
        handler = MessageHandler(
            registry=registry,
            dingtalk_client=mock_dingtalk,
        )
        msg = make_msg("触发崩溃")
        await handler.handle_incoming(msg)
        mock_dingtalk.send_text.assert_awaited_once()
        _, kwargs = mock_dingtalk.send_text.await_args
        assert "错误" in kwargs["content"]
