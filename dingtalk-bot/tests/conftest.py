"""测试共享 Fixtures。"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """测试用配置。"""
    return Settings(
        dingtalk={
            "app_key": "test_app_key",
            "app_secret": "test_app_secret",
            "bot_code": "test_bot_code",
        },
        llm={
            "provider": "claude",
            "anthropic_api_key": "sk-test-fake-key",
        },
        session={
            "backend": "memory",
        },
        log_level="DEBUG",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """测试用 FastAPI 应用实例。"""
    app = create_app()
    app.state.settings = settings
    return app


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """HTTP 异步测试客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
