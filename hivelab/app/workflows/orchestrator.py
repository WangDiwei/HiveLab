"""项目编排器：驱动一次完整的多 Agent 协作。

合作式单线程循环（非并行线程），带步骤上限，避免死锁与竞态；每个 Agent 的
step() 只有在确有进展时才返回 True，循环据此判定是否可结束。

可替换的扩展点：
- 消息轮询 → 事件驱动（替换 MessageHub.poll_once 或让 Agent 监听事件）
- SQLite → PostgreSQL（替换 Repository）
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..agents.deliverer import DelivererAgent
from ..agents.executer import ExecuteAgent
from ..agents.planner import PlannerAgent
from ..agents.runtime import AgentContext, AgentRole
from ..config import Settings
from ..llm.base import LLMClient
from ..llm.factory import build_default_client
from ..messaging.service import MessageHub
from ..storage.database import Database
from ..storage.repository import Repository
from ..tasks.service import TaskManager, TaskStatus
from ..utils.logging import AgentLogger, setup_logging

MAX_STEPS = 300
ACTIVE_STATES = {
    TaskStatus.PENDING.value,
    TaskStatus.ASSIGNED.value,
    TaskStatus.IN_PROGRESS.value,
    TaskStatus.BLOCKED.value,
    TaskStatus.FAILED.value,
}


def slugify(name: str) -> str:
    """把名称转成安全的目录片段。"""
    s = re.sub(r"[^\w\-\u4e00-\u9fa5]+", "_", name).strip("_")
    return s[:24] or "project"


class Orchestrator:
    """承载一个项目全生命周期，并对外暴露提交/查询接口。"""

    def __init__(
        self,
        settings: Settings,
        *,
        db: Database | None = None,
        llm: LLMClient | None = None,
        response_factory=None,
    ) -> None:
        setup_logging()
        self.settings = settings
        self.db = db or Database(settings.resolve_db_path)
        self.repo = Repository(self.db)
        self.hub = MessageHub(self.repo)
        self.tasks = TaskManager(self.repo)
        self.llm = llm or build_default_client(settings, response_factory=response_factory)
        self._logger = AgentLogger("workflow")
        self._planner: PlannerAgent | None = None
        self._deliverer: DelivererAgent | None = None
        self._executors: list[ExecuteAgent] = []

    def close(self) -> None:
        self.db.close()

    # ---------- 公开 API ----------
    def submit(
        self,
        requirement: str,
        extra_langs: list[str] | None = None,
        project_id: int | None = None,
    ) -> dict[str, Any]:
        """从零承载一次完整协作：需求 -> 规划 -> 执行 -> 交付。

        :param project_id: 可选；若给定则复用该项目记录（避免重复建项目，供 Web/后台使用）。
        """
        requirement = (requirement or "").strip()
        if not requirement:
            raise ValueError("需求不能为空")

        if project_id is None:
            project_id = self.repo.create_project(requirement, status="created")
        else:
            if self.repo.get_project(project_id) is None:
                raise ValueError(f"项目 {project_id} 不存在")
            self.repo.update_project(
                project_id, requirement=requirement, status="created"
            )
        self.project_id = project_id
        project_name = self._project_name(requirement, project_id)
        workspace = self.settings.resolve_workspace_root / f"{project_id}_{slugify(project_name)}"
        workspace.mkdir(parents=True, exist_ok=True)

        ctx = AgentContext(
            repo=self.repo,
            hub=self.hub,
            tasks=self.tasks,
            llm=self.llm,
            project_id=project_id,
            project_name=project_name,
            requirement=requirement,
            workspace_dir=workspace,
        )
        self._setup_agents(ctx)

        # 1) 规划并创建执行 Agent + 任务
        assignments = self._planner.plan_and_spawn()
        # 2) 创建协作群并拉起交付者
        delivery_id = self._deliverer.agent_id
        self._planner.create_collab_group(deliverer_id=delivery_id)
        self._spawn_executors(assignments, ctx)

        # 3) 合作式协作循环
        self._run_loop()

        # 4) 交付
        report = self._deliverer.deliver(extra_langs)
        report["project_id"] = project_id
        return report

    # ---------- 私有实现 ----------
    def _setup_agents(self, ctx: AgentContext) -> None:
        # 规划者
        p_id = self.repo.create_agent("规划者 Agent", AgentRole.PLANNER, ctx.project_id,
                                      description="负责需求分析与任务拆解分配")
        self._planner = PlannerAgent(ctx, "规划者 Agent", p_id, AgentLogger("planner"))
        # 交付者
        d_id = self.repo.create_agent("交付者 Agent", AgentRole.DELIVERER, ctx.project_id,
                                      description="负责检查交付、生成 README")
        self._deliverer = DelivererAgent(ctx, "交付者 Agent", d_id, AgentLogger("deliverer"))

    def _spawn_executors(self, assignments: list[tuple[int, int]], ctx: AgentContext) -> None:
        for task_id, agent_id in assignments:
            agent = self.repo.get_agent(agent_id)
            if not any(e.agent_id == agent_id for e in self._executors):
                task = self.tasks.get_task(task_id)
                role = "执行"
                ex = ExecuteAgent(ctx, agent["name"], agent_id, AgentLogger("executer"), role=role or "执行")
                self._executors.append(ex)

    def _run_loop(self) -> None:
        retried: dict[int, int] = {}
        steps = 0
        while steps < MAX_STEPS:
            progressed = False
            for ex in self._executors:
                if ex.step():
                    progressed = True
            if self._monitor(retried):
                progressed = True
            steps += 1
            if not self._has_active_tasks():
                break
            if not progressed:
                # 无进展保护：避免死锁
                self._logger.info("", "", "本轮回合无进展，提前结束")
                break

    def _monitor(self, retried: dict[int, int]) -> bool:
        """规划者监控：处理失败/阻塞任务（重试与重新分配），并汇总进度。"""
        acted = False
        for project_tasks in (self.repo.list_tasks(self.project_id),):
            for t in project_tasks:
                if t["status"] == TaskStatus.FAILED.value:
                    retried[t["id"]] = retried.get(t["id"], 0) + 1
                    if retried[t["id"]] > 3:
                        continue
                    self.tasks.retry(t["id"])
                    acted = True
                elif t["status"] == TaskStatus.BLOCKED.value:
                    if self.tasks.dependencies_ready(t["id"]):
                        self.tasks.retry(t["id"])
                        acted = True
        return acted

    def _has_active_tasks(self) -> bool:
        return any(
            t["status"] in ACTIVE_STATES for t in self.repo.list_tasks(self.project_id)
        )

    @staticmethod
    def _project_name(requirement: str, project_id: int) -> str:
        base = re.sub(r"\s+", " ", requirement).strip()[:20]
        return base or f"项目_{project_id}"

    # ---------- 查询接口（供 CLI / Web / GUI 复用） ----------
    def project_status(self, project_id: int) -> dict[str, Any] | None:
        p = self.repo.get_project(project_id)
        if p is None:
            return None
        p["tasks"] = self.repo.list_tasks(project_id)
        p["agents"] = self.repo.list_agents(project_id)
        return p

    def list_projects(self) -> list[dict]:
        return self.repo.list_projects()

    def list_dm_for(self, agent_id: int) -> list[dict]:
        return self.repo.list_direct_messages_for(agent_id)

    def last_report(self, project_id: int) -> dict:
        """取该项目最近一次交付的元数据（若无则给简要状态）。"""
        arts = self.repo.list_artifacts(project_id)
        tasks = self.repo.list_tasks(project_id)
        agents = self.repo.list_agents(project_id)
        project = self.repo.get_project(project_id) or {}
        return {
            "project_id": project_id,
            "requirement": project.get("requirement", ""),
            "status": project.get("status", ""),
            "result_path": project.get("result_path", ""),
            "agents": agents,
            "tasks": tasks,
            "artifacts": arts,
        }