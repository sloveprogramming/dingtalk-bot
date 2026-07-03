"""LLM 提供者单元测试（使用 Mock）。"""

from __future__ import annotations

from typing import AsyncIterator

import pytest

from app.core.llm.base import LLMMessage, LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    """测试用 Mock LLM 提供者。"""

    def __init__(self, response_text: str = "你好！我是 AI 助手。") -> None:
        self.response_text = response_text
        self.last_messages: list[LLMMessage] = []
        self.last_system: str | None = None

    async def chat(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        self.last_messages = messages
        self.last_system = system
        # 模拟 token 计数：输入 10 token，输出 ~len/2 token
        input_tokens = sum(len(m.content) // 2 + 1 for m in messages)
        output_tokens = len(self.response_text) // 2 + 1
        return LLMResponse(
            content=self.response_text,
            usage={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        )

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        for char in self.response_text:
            yield char


class TestLLMBase:
    """LLM 基类与 Mock 测试。"""

    @pytest.fixture
    def provider(self) -> MockLLMProvider:
        return MockLLMProvider()

    async def test_chat_simple(self, provider: MockLLMProvider):
        """测试简单的对话请求。"""
        response = await provider.chat(
            messages=[LLMMessage(role="user", content="你好")]
        )
        assert response.content == "你好！我是 AI 助手。"
        assert response.finish_reason == "stop"

    async def test_chat_with_system_prompt(self, provider: MockLLMProvider):
        """测试携带系统提示词的对话。"""
        await provider.chat(
            messages=[LLMMessage(role="user", content="告诉我天气")],
            system="你是一个天气助手",
        )
        assert provider.last_system == "你是一个天气助手"
        assert len(provider.last_messages) == 1

    async def test_chat_with_multi_turn(self, provider: MockLLMProvider):
        """测试多轮对话上下文。"""
        messages = [
            LLMMessage(role="user", content="你好"),
            LLMMessage(role="assistant", content="你好！有什么可以帮助你的？"),
            LLMMessage(role="user", content="北京天气怎么样？"),
        ]
        await provider.chat(messages=messages)
        assert len(provider.last_messages) == 3

    async def test_chat_tokens_in_response(self, provider: MockLLMProvider):
        """响应中应包含 Token 统计。"""
        response = await provider.chat(
            messages=[LLMMessage(role="user", content="test")]
        )
        assert response.total_tokens > 0
        assert response.input_tokens > 0
        assert response.output_tokens > 0

    async def test_chat_stream(self, provider: MockLLMProvider):
        """测试流式响应。"""
        collected = []
        async for chunk in provider.chat_stream(
            messages=[LLMMessage(role="user", content="hi")]
        ):
            collected.append(chunk)
        assert "".join(collected) == provider.response_text

    async def test_empty_messages(self, provider: MockLLMProvider):
        """空消息列表应正常处理。"""
        response = await provider.chat(messages=[])
        assert response.content == provider.response_text

    def test_count_tokens_default(self):
        """默认 token 计数实现。"""
        provider = MockLLMProvider()
        # 10 个字符 → 至少 5+1=6 tokens
        count = provider.count_tokens("你好世界")
        assert count >= 1

    async def test_chat_custom_params(self, provider: MockLLMProvider):
        """自定义参数的对话。"""
        response = await provider.chat(
            messages=[LLMMessage(role="user", content="test")],
            max_tokens=500,
            temperature=0.5,
        )
        assert response.content is not None
