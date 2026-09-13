"""统一日志与时间工具。

提供：
- ``now_utc()/now_utc_str()``：UTC 时间（ISO 字符串，可排序）。
- 结构化日志上下文，用于把 agent / task / 异常堆栈写入日志与数据库审计表。
"""

from __future__ import annotations

import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-7s | %(name)s"
    " | agent=%(agent_name)s | task=%(task_id)s | %(message)s"
)


def now_utc() -> datetime:
    """当前 UTC 时间的可排序 ISO 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def now_utc_str() -> str:
    return now_utc()


# 当前 agent / 任务上下文（用于日志附加字段）
current_agent: ContextVar[str] = ContextVar("agent", default="")
current_task: ContextVar[str] = ContextVar("task", default="")


class AgentFilter(logging.Filter):
    """为日志记录附加 agent/task 上下文与堆栈。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.agent_name = current_agent.get()
        record.task_id = current_task.get()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """配置全局日志：输出到 stderr，带结构化字段。"""
    root = logging.getLogger("hivelab")
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler.addFilter(AgentFilter())
    root.addHandler(handler)
    root.setLevel(level)


class AgentLogger:
    """封装带 agent/task 上下文的日志，同时可用于写业务审计。"""

    def __init__(self, name: str, module: str = "") -> None:
        self._logger = logging.getLogger(f"hivelab.{name}")
        self._module = module or name

    def _log(self, level, agent: str, task_id: int | str, msg: str, exc=None) -> None:
        token_a = current_agent.set(agent or "")
        token_t = current_task.set(str(task_id) if task_id else "")
        try:
            self._logger.log(level, msg, exc_info=exc)
        finally:
            current_agent.reset(token_a)
            current_task.reset(token_t)

    def info(self, agent: str, task_id: int | str, msg: str) -> None:
        self._log(logging.INFO, agent, task_id, msg)

    def warn(self, agent: str, task_id: int | str, msg: str) -> None:
        self._log(logging.WARNING, agent, task_id, msg)

    def error(self, agent: str, task_id: int | str, msg: str, exc: BaseException | None = None) -> None:
        self._log(logging.ERROR, agent, task_id, msg, exc)


def format_exc(exc: BaseException) -> str:
    """把异常转成便于入库的堆栈字符串。"""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def utc_to_local_str(iso: str) -> str:
    """把 UTC ISO 时间转成本地可读文本（降级时原样返回）。"""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso