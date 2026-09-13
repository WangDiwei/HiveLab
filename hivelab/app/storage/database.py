"""数据库封装与建表。

优先使用 SQLite；所有 DAO 只依赖本模块的 Database 层，未来可替换为 PostgreSQL。
时间统一以 UTC ISO-8601 字符串存储，字符串比较即时间比较。
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA_SCRIPT = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'created',
    created_at  TEXT NOT NULL,
    result_path TEXT NOT NULL DEFAULT '',
    extra_langs TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS agents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL DEFAULT 0,
    name        TEXT NOT NULL,
    role_type   TEXT NOT NULL DEFAULT 'executer',
    status      TEXT NOT NULL DEFAULT 'idle',
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    last_seen_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tasks (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id     INTEGER NOT NULL DEFAULT 0,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    creator_id     INTEGER NOT NULL DEFAULT 0,
    assignee_id    INTEGER NOT NULL DEFAULT 0,
    priority       INTEGER NOT NULL DEFAULT 5,
    status         TEXT NOT NULL DEFAULT 'pending',
    dependencies   TEXT NOT NULL DEFAULT '[]',
    created_at     TEXT NOT NULL,
    started_at     TEXT NOT NULL DEFAULT '',
    completed_at   TEXT NOT NULL DEFAULT '',
    artifacts_json TEXT NOT NULL DEFAULT '[]',
    error          TEXT NOT NULL DEFAULT '',
    progress       TEXT NOT NULL DEFAULT '',
    completion_definition TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS direct_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL DEFAULT 0,
    sender_id   INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'sent',
    priority    INTEGER NOT NULL DEFAULT 5,
    is_read     INTEGER NOT NULL DEFAULT 0,
    needs_reply INTEGER NOT NULL DEFAULT 0,
    reply_to_id INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS group_chats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL DEFAULT 0,
    name       TEXT NOT NULL,
    creator_id INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS group_members (
    chat_id   INTEGER NOT NULL,
    agent_id  INTEGER NOT NULL,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (chat_id, agent_id)
);

CREATE TABLE IF NOT EXISTS group_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id      INTEGER NOT NULL,
    sender_id    INTEGER NOT NULL,
    content      TEXT NOT NULL,
    mentions_json TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'sent'
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id   INTEGER NOT NULL,
    project_id INTEGER NOT NULL DEFAULT 0,
    task_id    INTEGER NOT NULL DEFAULT 0,
    action     TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL DEFAULT 0,
    task_id     INTEGER NOT NULL DEFAULT 0,
    agent_id    INTEGER NOT NULL,
    path        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS error_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    level      TEXT NOT NULL DEFAULT 'ERROR',
    module     TEXT NOT NULL DEFAULT '',
    agent_name TEXT NOT NULL DEFAULT '',
    project_id INTEGER NOT NULL DEFAULT 0,
    task_id    INTEGER NOT NULL DEFAULT 0,
    message    TEXT NOT NULL DEFAULT '',
    stack      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    level      TEXT NOT NULL DEFAULT 'INFO',
    module     TEXT NOT NULL DEFAULT '',
    agent_name TEXT NOT NULL DEFAULT '',
    project_id INTEGER NOT NULL DEFAULT 0,
    task_id    INTEGER NOT NULL DEFAULT 0,
    content    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_dm_receiver ON direct_messages(receiver_id);
CREATE INDEX IF NOT EXISTS idx_gm_chat ON group_messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_ar_agent ON agent_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_el_level ON error_logs(level);
"""


class Database:
    """SQLite 数据库封装，线程安全，自动建表。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._in_tx = False
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self.init_schema()

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA_SCRIPT)
            self._conn.commit()

    def execute(self, sql: str, params: tuple = (), commit: bool | None = None) -> sqlite3.Cursor:
        """执行写入/单条查询。事务内不自动提交，事务外按需提交。"""
        with self._lock:
            cur = self._conn.execute(sql, params)
            if commit is not False and not self._in_tx:
                self._conn.commit()
            return cur

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchone()

    def transaction(self):
        """返回事务上下文管理器。"""
        return _Transaction(self)

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.ProgrammingError:
                pass


class _Transaction:
    def __init__(self, db: Database):
        self._db = db

    def __enter__(self):
        self._db._in_tx = True
        self._db.execute("BEGIN", commit=False)
        return self._db

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._db.execute("COMMIT", commit=False)
            else:
                self._db.execute("ROLLBACK", commit=False)
        finally:
            self._db._in_tx = False
        return False