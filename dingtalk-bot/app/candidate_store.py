"""候选人状态持久化存储（SQLite）。

记录每个候选人所在群、入群时间、测试完成状态。
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "candidates.db"


class CandidateStore:
    """候选人状态存储。"""

    _instance: CandidateStore | None = None
    _lock = threading.Lock()

    def __new__(cls) -> CandidateStore:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接。"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._local.conn = sqlite3.connect(str(DB_PATH))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self) -> None:
        """初始化数据库表。"""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT '',
                user_name TEXT NOT NULL DEFAULT '',
                group_id TEXT NOT NULL,
                cid TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                joined_at TEXT NOT NULL,
                completed_at TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_candidate_group
            ON candidates(user_id, group_id)
        """)
        # 兼容旧表：添加 cid 列（如果不存在）
        try:
            conn.execute("ALTER TABLE candidates ADD COLUMN cid TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # 列已存在
        conn.commit()

    def add_candidate(
        self,
        user_id: str,
        user_name: str,
        group_id: str,
        group_name: str = "",
    ) -> None:
        """添加候选人记录（入群时调用）。"""
        now = datetime.now().isoformat()
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO candidates
            (user_id, user_name, group_id, status, joined_at, updated_at)
            VALUES (?, ?, ?, 'pending', ?, ?)
        """, (user_id, user_name, group_id, now, now))
        conn.commit()
        logger.info("候选人已记录: %s -> 群 %s", user_name or user_id, group_id)

    def mark_completed(self, group_id: str, user_name: str = "") -> bool:
        """将候选人标记为已完成（按群 ID 匹配）。

        Args:
            group_id: 群会话 ID。
            user_name: 候选人姓名（可更新）。

        Returns:
            是否更新成功。
        """
        now = datetime.now().isoformat()
        conn = self._get_conn()
        if user_name:
            cursor = conn.execute("""
                UPDATE candidates
                SET status = 'completed', completed_at = ?, updated_at = ?, user_name = ?
                WHERE cid = ? OR group_id = ?
            """, (now, now, user_name, group_id, group_id))
        else:
            cursor = conn.execute("""
                UPDATE candidates
                SET status = 'completed', completed_at = ?, updated_at = ?
                WHERE cid = ? OR group_id = ?
            """, (now, now, group_id, group_id))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info("候选人已标记完成: %s", group_id)
            return True
        logger.warning("未找到候选人记录: group=%s", group_id)
        return False

    def update_candidate_info(self, cid: str, user_name: str) -> bool:
        """更新候选人的 cid 和姓名。
        按 cid 精确匹配，匹配不到则更新第一条无 real_name 的记录。
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE candidates SET cid = ?, user_name = ? WHERE cid = ?",
            (cid, user_name, cid),
        )
        if cursor.rowcount == 0:
            cursor = conn.execute(
                "UPDATE candidates SET cid = ?, user_name = ? "
                "WHERE rowid IN (SELECT rowid FROM candidates "
                "WHERE (cid IS NULL OR cid = '') AND length(user_id) > 10 LIMIT 1)",
                (cid, user_name),
            )
        conn.commit()
        if cursor.rowcount > 0:
            logger.info("候选人信息已更新: cid=%s, name=%s", cid[:20], user_name)
            return True
        return False

    def remove_candidate(self, group_id: str) -> bool:
        """候选人退群时，删除其记录（按群 ID）。

        Returns:
            是否删除成功。
        """
        conn = self._get_conn()
        cursor = conn.execute("""
            DELETE FROM candidates WHERE group_id = ?
        """, (group_id,))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info("候选人记录已删除: group=%s", group_id)
            return True
        logger.info("未找到要删除的记录: group=%s", group_id)
        return False

    def get_group_status(self, group_id: str) -> list[dict[str, Any]]:
        """获取某个群的所有候选人状态。

        Args:
            group_id: 群会话 ID。

        Returns:
            候选人状态列表，按状态排序（未完成的在前）。
        """
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT user_name, user_id, status, joined_at, completed_at
            FROM candidates
            WHERE group_id = ?
            ORDER BY
                CASE status WHEN 'completed' THEN 1 ELSE 0 END,
                joined_at ASC
        """, (group_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_all_candidates(self) -> list[dict[str, Any]]:
        """获取所有候选人的状态（全部群），按群分组。

        Returns:
            所有候选人状态列表，按群分组、按状态排序。
        """
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT user_name, user_id, group_id, status, joined_at, completed_at
            FROM candidates
            ORDER BY group_id ASC,
                CASE status WHEN 'completed' THEN 1 ELSE 0 END,
                joined_at ASC
        """).fetchall()
        return [dict(row) for row in rows]

    def get_all_groups(self) -> list[str]:
        """获取有候选人的所有群 ID。"""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT DISTINCT group_id FROM candidates ORDER BY group_id
        """).fetchall()
        return [row["group_id"] for row in rows]
