"""Anthropic Claude API 实现。"""

from __future__ import annotations

from typing import AsyncIterator

from anthropic import AsyncAnthropic

from app.core.llm.base import LLMMessage, LLMProvider, LLMResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeProvider(LLMProvider):
    """基于 Anthropic Claude API 的 LLM 提供者。"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._default_max_tokens = max_tokens
        self._default_temperature = temperature

    async def chat(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """调用 Claude API 获取回复。

        Args:
            messages: 对话历史（user / assistant 交替）。
            system: 系统提示词。
            max_tokens: 最大生成长度。
            temperature: 生成温度。

        Returns:
            LLMResponse 包含生成文本和用量统计。
        """
        try:
            response = await self._client.messages.create(
                model=self._model,
                system=system,
                max_tokens=max_tokens or self._default_max_tokens,
                temperature=temperature or self._default_temperature,
                messages=[{"role": m.role, "content": m.content} for m in messages],
            )
        except Exception as exc:
            logger.error("Claude API 调用失败: %s", exc)
            raise

        # 处理多种 content block 类型（TextBlock, ThinkingBlock 等）
        text_parts = []
        if response.content:
            for block in response.content:
                block_type = getattr(block, "type", "")
                if block_type == "text" or hasattr(block, "text"):
                    text_parts.append(block.text)
                elif block_type == "thinking" or hasattr(block, "thinking"):
                    logger.debug("跳过 ThinkingBlock")
                else:
                    logger.debug("未知 content block 类型: %s", block_type)
        content = "".join(text_parts)

        return LLMResponse(
            content=content,
            finish_reason=response.stop_reason or "stop",
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            },
        )

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """流式调用 Claude API。"""
        try:
            async with self._client.messages.stream(
                model=self._model,
                system=system,
                max_tokens=max_tokens or self._default_max_tokens,
                temperature=temperature or self._default_temperature,
                messages=[{"role": m.role, "content": m.content} for m in messages],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:
            logger.error("Claude 流式调用失败: %s", exc)
            raise
