"""应用配置 —— 通过环境变量 / .env 文件加载。"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DingTalkSettings(BaseSettings):
    """钉钉开放平台应用配置。"""

    model_config = SettingsConfigDict(env_prefix="DINGTALK__", extra="ignore")

    app_key: str = ""
    """应用的 AppKey / ClientId。"""

    app_secret: str = ""
    """应用的 AppSecret / ClientSecret。"""

    bot_code: str = ""
    """机器人编码，在钉钉开放平台机器人配置页查看。"""

    @property
    def is_configured(self) -> bool:
        """是否已配置钉钉参数（用于检查启动就绪状态）。"""
        return bool(self.app_key and self.app_secret)


class LLMSettings(BaseSettings):
    """大语言模型配置。"""

    model_config = SettingsConfigDict(env_prefix="LLM__")

    provider: str = "claude"
    """LLM 提供者: claude | openai | custom。"""

    anthropic_api_key: str | None = None
    """Anthropic Claude API 密钥。"""

    anthropic_model: str = "claude-sonnet-4-20250514"
    """Claude 模型名称。"""

    max_tokens: int = 2048
    """每次 LLM 调用的最大生成长度。"""

    temperature: float = 0.7
    """生成温度。"""

    system_prompt: str = (
        "你是一个专业的智能客服助手，负责回答用户的问题。"
        "请用友好、专业的态度回复用户。回答要简洁准确，"
        "如果不知道答案，请如实告知用户。"
    )


class SessionSettings(BaseSettings):
    """会话管理配置。"""

    model_config = SettingsConfigDict(env_prefix="SESSION__")

    backend: str = "memory"
    """会话存储后端: memory | redis。"""

    ttl_minutes: int = 30
    """会话过期时间（分钟）。"""

    max_context_tokens: int = 100_000
    """会话上下文最大 Token 数（超出后从旧到新裁剪）。"""

    redis_url: str | None = None
    """Redis 连接 URL，仅在 backend=redis 时使用。"""


class Settings(BaseSettings):
    """全局应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dingtalk: DingTalkSettings = Field(default_factory=DingTalkSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)

    authorized_users: list[str] = []
    """有权限查看候选人状态的用户 UserId 列表（HR/开发者）。"""

    @field_validator("authorized_users", mode="before")
    @classmethod
    def split_authorized_users(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [uid.strip() for uid in v.split(",") if uid.strip()]
        return v

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    @property
    def debug(self) -> bool:
        return self.log_level.upper() == "DEBUG"
