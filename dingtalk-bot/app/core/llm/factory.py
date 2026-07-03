"""LLM 提供者工厂 —— 根据配置创建对应的 LLM 提供者实例。"""

from __future__ import annotations

from app.config import LLMSettings
from app.core.llm.base import LLMProvider
from app.core.llm.claude import ClaudeProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)


def build_llm_provider(settings: LLMSettings) -> LLMProvider:
    """根据配置构建 LLM 提供者。

    Args:
        settings: LLM 配置。

    Returns:
        配置好的 LLMProvider 实例。

    Raises:
        ValueError: 不支持的提供者类型。
    """
    provider_name = settings.provider.lower()

    if provider_name == "claude":
        if not settings.anthropic_api_key:
            logger.warning("Claude API 密钥未配置，LLM 功能将不可用")
        return ClaudeProvider(
            api_key=settings.anthropic_api_key or "",
            model=settings.anthropic_model,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
        )

    raise ValueError(f"不支持的 LLM 提供者: {provider_name}")
