"""管理端点 —— 会话查看、清理、插件列表等运维功能。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.core.dingtalk.client import DingTalkClient
from app.core.message.plugins.register import PluginRegistry
from app.core.session.manager import SessionManager
from app.dependencies import get_plugin_registry, get_session_manager
from app.group_events import GroupEventHandler

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """列出活跃会话。"""
    ids = await session_manager._store.list_ids(limit=limit, offset=offset)
    total = await session_manager._store.count()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sessions": ids,
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """查看单个会话详情。"""
    session = await session_manager._store.get(session_id)
    if session is None:
        return {"error": "会话不存在"}
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "user_nick": session.user_nick,
        "conversation_type": session.conversation_type,
        "message_count": session.message_count,
        "total_tokens": session.total_tokens,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "history": [
            {
                "role": entry.role,
                "content": entry.content[:200],  # 截断显示
                "timestamp": entry.timestamp.isoformat(),
                "token_count": entry.token_count,
            }
            for entry in session.history
        ],
    }


@router.delete("/sessions/{session_id}")
async def clear_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """清理指定会话。"""
    await session_manager.clear(session_id)
    return {"status": "ok", "message": "会话已清理"}


@router.delete("/sessions")
async def clear_all_sessions(
    session_manager: SessionManager = Depends(get_session_manager),
):
    """清理所有会话。"""
    await session_manager.clear_all()
    return {"status": "ok", "message": "所有会话已清理"}


@router.get("/plugins")
async def list_plugins(
    registry: PluginRegistry = Depends(get_plugin_registry),
):
    """列出已注册的插件。"""
    plugins = registry.list_plugins()
    return {
        "total": len(plugins),
        "plugins": [
            {"name": p.name, "description": p.description} for p in plugins
        ],
    }


@router.get("/stats")
async def get_stats(
    session_manager: SessionManager = Depends(get_session_manager),
):
    """获取运行时统计信息。"""
    stats = await session_manager.get_stats()
    return stats


@router.post("/test-welcome")
async def test_welcome(
    request: Request,
    group_id: str = Query(..., description="群 chatId"),
    user_name: str = Query("新同学", description="候选人名称"),
):
    """手动触发欢迎语（测试用）。"""
    group_handler: GroupEventHandler | None = getattr(
        request.app.state, "group_handler", None
    )
    if not group_handler:
        return {"error": "群事件处理器未初始化"}

    # 构造模拟事件数据
    from dingtalk_stream import EventMessage, AckMessage
    from dingtalk_stream.handlers import Headers

    event = EventMessage()
    event.headers = Headers()
    event.headers.event_type = "chat_add_member"
    event.data = {
        "chatId": group_id,
        "unionId": ["test_union_id"],
        "userName": user_name,
    }

    await group_handler._handle_member_add(event)
    return {"status": "ok", "message": f"欢迎语已发送到群 {group_id}，称呼: {user_name}"}
