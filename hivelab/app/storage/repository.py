"""数据访问层 Repository。

所有业务模块都通过 Repository 读写数据库，不直接接触 SQL/连接。
当前基于 SQLite；如需切换 PostgreSQL，仅需替换实现而保持接口不变。
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from .database import Database
from ..utils.logging import now_utc_str


def row_to_dict(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class Repository:
    """统一数据访问入口。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ---------- 项目 ----------
    def create_project(self, requirement: str, status: str = "created") -> int:
        cur = self._db.execute(
            "INSERT INTO projects (requirement, status, created_at) VALUES (?, ?, ?)",
            (requirement, status, now_utc_str()),
        )
        return int(cur.lastrowid)

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        return row_to_dict(
            self._db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
        )

    def list_projects(self) -> list[dict[str, Any]]:
        return [
            row_to_dict(r) for r in self._db.fetchall("SELECT * FROM projects ORDER BY id")
        ]

    def update_project(self, project_id: int, **fields: Any) -> None:
        self._update("projects", project_id, fields)

    # ---------- Agent ----------
    def create_agent(
        self, name: str, role_type: str, project_id: int = 0, description: str = ""
    ) -> int:
        cur = self._db.execute(
            "INSERT INTO agents (project_id, name, role_type, status, description, created_at)"
            " VALUES (?, ?, ?, 'idle', ?, ?)",
            (project_id, name, role_type, description, now_utc_str()),
        )
        return int(cur.lastrowid)

    def get_agent(self, agent_id: int) -> dict[str, Any] | None:
        return row_to_dict(self._db.fetchone("SELECT * FROM agents WHERE id=?", (agent_id,)))

    def list_agents(self, project_id: int | None = None) -> list[dict[str, Any]]:
        if project_id is None:
            rows = self._db.fetchall("SELECT * FROM agents ORDER BY id")
        else:
            rows = self._db.fetchall(
                "SELECT * FROM agents WHERE project_id=? ORDER BY id", (project_id,)
            )
        return [row_to_dict(r) for r in rows]

    def find_agent_by_name(self, name: str, project_id: int | None = None) -> dict[str, Any] | None:
        if project_id is None:
            row = self._db.fetchone("SELECT * FROM agents WHERE name=?", (name,))
        else:
            row = self._db.fetchone(
                "SELECT * FROM agents WHERE name=? AND project_id=?", (name, project_id)
            )
        return row_to_dict(row)

    def update_agent(self, agent_id: int, **fields: Any) -> None:
        self._update("agents", agent_id, fields)

    def set_agent_status(self, agent_id: int, status: str) -> None:
        self._db.execute(
            "UPDATE agents SET status=?, last_seen_at=? WHERE id=?",
            (status, now_utc_str(), agent_id),
        )

    # ---------- 任务 ----------
    def create_task(
        self,
        *,
        project_id: int,
        name: str,
        description: str,
        creator_id: int = 0,
        assignee_id: int = 0,
        priority: int = 5,
        dependencies: Sequence[int] | None = None,
        completion_definition: str = "",
    ) -> int:
        cur = self._db.execute(
            "INSERT INTO tasks (project_id, name, description, creator_id, assignee_id,"
            " priority, status, dependencies, created_at, completion_definition)"
            " VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
            (
                project_id,
                name,
                description,
                creator_id,
                assignee_id,
                priority,
                json.dumps(list(dependencies or [])),
                now_utc_str(),
                completion_definition,
            ),
        )
        return int(cur.lastrowid)

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        return row_to_dict(self._db.fetchone("SELECT * FROM tasks WHERE id=?", (task_id,)))

    def list_tasks(self, project_id: int | None = None) -> list[dict[str, Any]]:
        if project_id is None:
            rows = self._db.fetchall("SELECT * FROM tasks ORDER BY priority, id")
        else:
            rows = self._db.fetchall(
                "SELECT * FROM tasks WHERE project_id=? ORDER BY priority, id",
                (project_id,),
            )
        return [row_to_dict(r) for r in rows]

    def list_tasks_by_assignee(self, assignee_id: int) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            "SELECT * FROM tasks WHERE assignee_id=? ORDER BY priority, id", (assignee_id,)
        )
        return [row_to_dict(r) for r in rows]

    def list_tasks_by_status(self, status: str, project_id: int | None = None) -> list[dict[str, Any]]:
        if project_id is None:
            rows = self._db.fetchall(
                "SELECT * FROM tasks WHERE status=? ORDER BY id", (status,)
            )
        else:
            rows = self._db.fetchall(
                "SELECT * FROM tasks WHERE status=? AND project_id=? ORDER BY id",
                (status, project_id),
            )
        return [row_to_dict(r) for r in rows]

    def update_task(self, task_id: int, **fields: Any) -> None:
        self._update("tasks", task_id, fields)

    @staticmethod
    def parse_dependencies(task: dict[str, Any]) -> list[int]:
        try:
            return [int(x) for x in json.loads(task.get("dependencies", "[]"))]
        except (ValueError, TypeError):
            return []

    @staticmethod
    def parse_artifacts(task: dict[str, Any]) -> list[str]:
        try:
            return list(json.loads(task.get("artifacts_json", "[]")))
        except (ValueError, TypeError):
            return []

    # ---------- 私信 ----------
    def send_direct_message(
        self,
        *,
        sender_id: int,
        receiver_id: int,
        content: str,
        project_id: int = 0,
        priority: int = 5,
        needs_reply: int = 0,
        reply_to_id: int = 0,
    ) -> int:
        cur = self._db.execute(
            "INSERT INTO direct_messages (sender_id, receiver_id, content, project_id,"
            " created_at, status, priority, needs_reply, reply_to_id)"
            " VALUES (?, ?, ?, ?, ?, 'sent', ?, ?, ?)",
            (sender_id, receiver_id, content, project_id, now_utc_str(),
             priority, needs_reply, reply_to_id),
        )
        return int(cur.lastrowid)

    def get_direct_message(self, msg_id: int) -> dict[str, Any] | None:
        return row_to_dict(
            self._db.fetchone("SELECT * FROM direct_messages WHERE id=?", (msg_id,))
        )

    def list_direct_messages_for(
        self, receiver_id: int, unread_only: bool = False
    ) -> list[dict[str, Any]]:
        if unread_only:
            rows = self._db.fetchall(
                "SELECT * FROM direct_messages WHERE receiver_id=? AND is_read=0"
                " ORDER BY created_at, id",
                (receiver_id,),
            )
        else:
            rows = self._db.fetchall(
                "SELECT * FROM direct_messages WHERE receiver_id=?"
                " ORDER BY created_at, id",
                (receiver_id,),
            )
        return [row_to_dict(r) for r in rows]

    def list_direct_messages_between(
        self, a: int, b: int, limit: int = 200
    ) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            "SELECT * FROM direct_messages WHERE (sender_id=? AND receiver_id=?)"
            " OR (sender_id=? AND receiver_id=?) ORDER BY created_at, id LIMIT ?",
            (a, b, b, a, limit),
        )
        return [row_to_dict(r) for r in rows]

    def mark_direct_read(self, msg_id: int) -> None:
        self._db.execute(
            "UPDATE direct_messages SET is_read=1, status='read' WHERE id=?", (msg_id,)
        )

    def update_direct_message(self, msg_id: int, **fields: Any) -> None:
        self._update("direct_messages", msg_id, fields)

    # ---------- 群聊 ----------
    def create_group_chat(self, name: str, creator_id: int, project_id: int = 0) -> int:
        cur = self._db.execute(
            "INSERT INTO group_chats (project_id, name, creator_id, created_at)"
            " VALUES (?, ?, ?, ?)",
            (project_id, name, creator_id, now_utc_str()),
        )
        chat_id = int(cur.lastrowid)
        self.add_group_member(chat_id, creator_id)
        return chat_id

    def get_group_chat(self, chat_id: int) -> dict[str, Any] | None:
        return row_to_dict(
            self._db.fetchone("SELECT * FROM group_chats WHERE id=?", (chat_id,))
        )

    def list_group_chats(self, project_id: int | None = None) -> list[dict[str, Any]]:
        if project_id is None:
            rows = self._db.fetchall("SELECT * FROM group_chats ORDER BY id")
        else:
            rows = self._db.fetchall(
                "SELECT * FROM group_chats WHERE project_id=? ORDER BY id", (project_id,)
            )
        return [row_to_dict(r) for r in rows]

    def add_group_member(self, chat_id: int, agent_id: int) -> None:
        exists = self._db.fetchone(
            "SELECT 1 FROM group_members WHERE chat_id=? AND agent_id=?",
            (chat_id, agent_id),
        )
        if exists:
            return
        self._db.execute(
            "INSERT INTO group_members (chat_id, agent_id, joined_at) VALUES (?, ?, ?)",
            (chat_id, agent_id, now_utc_str()),
        )

    def remove_group_member(self, chat_id: int, agent_id: int) -> None:
        self._db.execute(
            "DELETE FROM group_members WHERE chat_id=? AND agent_id=?",
            (chat_id, agent_id),
        )

    def list_group_members(self, chat_id: int) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            "SELECT a.* FROM group_members m JOIN agents a ON a.id=m.agent_id"
            " WHERE m.chat_id=? ORDER BY m.joined_at",
            (chat_id,),
        )
        return [row_to_dict(r) for r in rows]

    def list_group_chats_for(self, agent_id: int) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            "SELECT c.* FROM group_members m JOIN group_chats c ON c.id=m.chat_id"
            " WHERE m.agent_id=? ORDER BY c.id",
            (agent_id,),
        )
        return [row_to_dict(r) for r in rows]

    def is_group_member(self, chat_id: int, agent_id: int) -> bool:
        row = self._db.fetchone(
            "SELECT 1 FROM group_members WHERE chat_id=? AND agent_id=?",
            (chat_id, agent_id),
        )
        return row is not None

    def send_group_message(
        self,
        chat_id: int,
        sender_id: int,
        content: str,
        mentions: Sequence[int] | None = None,
    ) -> int:
        cur = self._db.execute(
            "INSERT INTO group_messages (chat_id, sender_id, content, mentions_json,"
            " created_at, status) VALUES (?, ?, ?, ?, ?, 'sent')",
            (chat_id, sender_id, content, json.dumps(list(mentions or [])), now_utc_str()),
        )
        return int(cur.lastrowid)

    def get_group_message(self, msg_id: int) -> dict[str, Any] | None:
        return row_to_dict(
            self._db.fetchone("SELECT * FROM group_messages WHERE id=?", (msg_id,))
        )

    def list_group_messages(
        self, chat_id: int, after_id: int = 0, limit: int = 500
    ) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            "SELECT * FROM group_messages WHERE chat_id=? AND id>? ORDER BY id LIMIT ?",
            (chat_id, after_id, limit),
        )
        return [row_to_dict(r) for r in rows]

    def list_group_messages_mentioning(
        self, chat_id: int, agent_id: int, after_id: int = 0
    ) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            "SELECT * FROM group_messages WHERE chat_id=? AND mentions_json LIKE ? AND id>?"
            " ORDER BY id",
            (chat_id, f"%{agent_id}%", after_id),
        )
        return [row_to_dict(r) for r in rows]

    @staticmethod
    def parse_mentions(msg: dict[str, Any]) -> list[int]:
        try:
            return [int(x) for x in json.loads(msg.get("mentions_json", "[]"))]
        except (ValueError, TypeError):
            return []

    # ---------- 产物 ----------
    def add_artifact(self, project_id: int, task_id: int, agent_id: int, path: str, description: str) -> int:
        cur = self._db.execute(
            "INSERT INTO artifacts (project_id, task_id, agent_id, path, description, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, task_id, agent_id, path, description, now_utc_str()),
        )
        return int(cur.lastrowid)

    def list_artifacts(self, project_id: int | None = None, task_id: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM artifacts WHERE 1=1"
        params: list[Any] = []
        if project_id is not None:
            sql += " AND project_id=?"
            params.append(project_id)
        if task_id is not None:
            sql += " AND task_id=?"
            params.append(task_id)
        sql += " ORDER BY id"
        return [row_to_dict(r) for r in self._db.fetchall(sql, tuple(params))]

    # ---------- 执行记录 / 审计 ----------
    def add_agent_run(self, *, agent_id: int, project_id: int = 0, task_id: int = 0, action: str, detail: str = "") -> int:
        cur = self._db.execute(
            "INSERT INTO agent_runs (agent_id, project_id, task_id, action, detail, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (agent_id, project_id, task_id, action, detail[:4000], now_utc_str()),
        )
        return int(cur.lastrowid)

    def list_agent_runs(self, agent_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if agent_id is None:
            rows = self._db.fetchall("SELECT * FROM agent_runs ORDER BY id DESC LIMIT ?", (limit,))
        else:
            rows = self._db.fetchall(
                "SELECT * FROM agent_runs WHERE agent_id=? ORDER BY id DESC LIMIT ?",
                (agent_id, limit),
            )
        return [row_to_dict(r) for r in rows]

    # ---------- 日志 / 事件 ----------
    def add_error_log(
        self, *, level: str, module: str, agent_name: str = "", project_id: int = 0,
        task_id: int = 0, message: str = "", stack: str = "",
    ) -> int:
        cur = self._db.execute(
            "INSERT INTO error_logs (level, module, agent_name, project_id, task_id,"
            " message, stack, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (level, module, agent_name, project_id, task_id, message[:4000], stack[:8000], now_utc_str()),
        )
        return int(cur.lastrowid)

    def list_error_logs(self, level: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if level is None:
            rows = self._db.fetchall("SELECT * FROM error_logs ORDER BY id DESC LIMIT ?", (limit,))
        else:
            rows = self._db.fetchall(
                "SELECT * FROM error_logs WHERE level=? ORDER BY id DESC LIMIT ?", (level, limit)
            )
        return [row_to_dict(r) for r in rows]

    def add_event(
        self, *, level: str = "INFO", module: str, agent_name: str = "", project_id: int = 0,
        task_id: int = 0, content: str = "",
    ) -> int:
        cur = self._db.execute(
            "INSERT INTO system_events (level, module, agent_name, project_id, task_id,"
            " content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (level, module, agent_name, project_id, task_id, content[:4000], now_utc_str()),
        )
        return int(cur.lastrowid)

    def list_events(self, limit: int = 300, project_id: int | None = None) -> list[dict[str, Any]]:
        if project_id is None:
            rows = self._db.fetchall("SELECT * FROM system_events ORDER BY id DESC LIMIT ?", (limit,))
        else:
            rows = self._db.fetchall(
                "SELECT * FROM system_events WHERE project_id=? ORDER BY id DESC LIMIT ?",
                (project_id, limit),
            )
        return [row_to_dict(r) for r in rows]

    # ---------- 通用 ----------
    def _update(self, table: str, row_id: int, fields: dict[str, Any]) -> None:
        if not fields:
            return
        allowed = _ALLOWED_COLS.get(table)
        assignments = []
        params: list[Any] = []
        for k, v in fields.items():
            if allowed is not None and k not in allowed:
                continue
            assignments.append(f"{k}=?")
            params.append(v)
        if not assignments:
            return
        params.append(row_id)
        self._db.execute(
            f"UPDATE {table} SET {', '.join(assignments)} WHERE id=?", tuple(params)
        )


_ALLOWED_COLS: dict[str, set[str]] = {
    "projects": {"requirement", "status", "result_path", "extra_langs"},
    "agents": {"name", "role_type", "status", "description", "last_seen_at", "project_id"},
    "tasks": {
        "name", "description", "creator_id", "assignee_id", "priority", "status",
        "dependencies", "started_at", "completed_at", "artifacts_json", "error", "progress",
        "completion_definition",
    },
    "direct_messages": {"status", "is_read", "priority", "needs_reply", "content"},
    "group_chats": {"name"},
    "group_messages": {"status"},
}