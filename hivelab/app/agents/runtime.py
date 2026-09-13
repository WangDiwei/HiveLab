"""Agent 运行时基类与上下文。

BaseAgent 只依赖抽象服务（LLM / 消息 / 任务 / 存储），不依赖具体服务商。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..llm.base import LLMClient
from ..messaging.service import MessageHub
from ..storage.repository import Repository
from ..tasks.service import TaskManager
from ..utils.logging import AgentLogger


@dataclass
class AgentContext:
    """共享给所有 Agent 的服务依赖。"""

    repo: Repository
    hub: MessageHub
    tasks: TaskManager
    llm: LLMClient
    project_id: int
    project_name: str
    requirement: str
    workspace_dir: Path  # 当前项目专用目录
    group_chat_id: int = 0  # 项目协作群


class AgentRole:
    """Agent 角色常量。"""

    PLANNER = "planner"
    EXECUTER = "executer"
    DELIVERER = "deliverer"


class BaseAgent:
    """所有 Agent 的公共基类。"""

    role_type = AgentRole.EXECUTER

    def __init__(
        self,
        ctx: AgentContext,
        name: str,
        agent_id: int,
        logger: AgentLogger,
    ) -> None:
        self.ctx = ctx
        self.name = name
        self.agent_id = agent_id
        self._logger = logger

    # ---- 便捷访问 ----
    @property
    def repo(self) -> Repository:
        return self.ctx.repo

    @property
    def hub(self) -> MessageHub:
        return self.ctx.hub

    @property
    def tasks(self) -> TaskManager:
        return self.ctx.tasks

    @property
    def llm(self) -> LLMClient:
        return self.ctx.llm

    @property
    def project_id(self) -> int:
        return self.ctx.project_id

    @property
    def workspace(self) -> Path:
        return self.ctx.workspace_dir

    # ---- 工具 ----
    def audit(self, action: str, detail: str = "", task_id: int = 0) -> None:
        """记录一次 Agent 行为（用于审计与排障）。"""
        self.repo.add_agent_run(
            agent_id=self.agent_id,
            project_id=self.project_id,
            task_id=task_id,
            action=action,
            detail=detail,
        )
        self.repo.add_event(
            module=self.role_type,
            agent_name=self.name,
            project_id=self.project_id,
            task_id=task_id,
            content=f"{action}: {detail[:200]}",
        )

    def log_info(self, action: str, task_id: int = 0, detail: str = "") -> None:
        self._logger.info(self.name, task_id, detail or action)

    def log_error(self, action: str, task_id: int = 0, detail: str = "", exc: BaseException | None = None) -> None:
        self._logger.error(self.name, task_id, detail or action, exc)
        self.repo.add_error_log(
            level="ERROR",
            module=self.role_type,
            agent_name=self.name,
            project_id=self.project_id,
            task_id=task_id,
            message=detail or action,
        )

    def send_group(self, chat_id: int, content: str, mention_ids: list[int] | None = None) -> int:
        return self.hub.send_group(chat_id, self.agent_id, content, mention_ids)

    def send_dm(self, receiver_id: int, content: str, needs_reply: int = 0, priority: int = 5) -> int:
        return self.hub.send_dm(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            content=content,
            project_id=self.project_id,
            needs_reply=needs_reply,
            priority=priority,
        )