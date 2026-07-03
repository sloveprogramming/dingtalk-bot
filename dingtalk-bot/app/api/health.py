"""健康检查端点。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """存活检查 —— 用于 Docker/K8s 健康探测。"""
    return {"status": "ok", "version": "0.1.0"}


@router.get("/health/ready")
async def readiness_check():
    """就绪检查 —— 确认依赖服务（Redis 等）是否可用。"""
    # TODO: 后续可在此处检查 Redis 连接、DingTalk 等依赖
    return {"ready": True, "services": {"dingtalk": "pending", "redis": "pending"}}
