"""LLM 提供者抽象基类。

定义所有 LLM 提供者必须实现的接口，支持多种 LLM 后端无缝切换。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class LLMMessage:
    """LLM 对话消息。"""

    role: str
    """角色: user / assistant。"""

    content: str
    """消息内容。"""


@dataclass
class LLMResponse:
    """LLM 响应。"""

    content: str
    """生成的文本内容。"""

    finish_reason: str = "stop"
    """完成原因: stop / length / content_filter。"""

    usage: dict = field(default_factory=dict)
    """Token 使用统计。"""

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)

    @property
    def input_tokens(self) -> int:
        return self.usage.get("input_tokens", 0)

    @property
    def output_tokens(self) -> int:
        return self.usage.get("output_tokens", 0)


class LLMProvider(abc.ABC):
    """LLM 提供者抽象基类。"""

    @abc.abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """发送对话请求，获取完整响应。

        Args:
            messages: 对话消息列表。
            system: 系统提示词。
            max_tokens: 最大生成 Token 数。
            temperature: 生成温度。

        Returns:
            LLM 响应。
        """

    @abc.abstractmethod
    async def chat_stream(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """流式对话请求。

        Args:
            messages: 对话消息列表。
            system: 系统提示词。
            max_tokens: 最大生成 Token 数。
            temperature: 生成温度。

        Yields:
            逐片段的文本内容。
        """

    def count_tokens(self, text: str) -> int:
        """估算文本的 Token 数。

        默认实现: 按字符数简单估算（中文约 1 token/1.5 字符，英文约 1 token/4 字符）。
        具体 LLM 提供者可覆盖此方法提供更精确的计数。

        Args:
            text: 待估算的文本。

        Returns:
            估算的 Token 数。
        """
        # 简单估算：混合中英文场景，平均约 1 token / 2.5 字符
        return max(1, len(text) // 2 + 1)
