"""交付者 Agent：收集产物、检查需求、生成 README、冒烟测试、交付。"""

from __future__ import annotations

from ..delivery.readme import write_readmes
from ..delivery.smoke import SmokeTester
from ..tasks.service import TaskStatus
from .runtime import AgentRole, BaseAgent


class DelivererAgent(BaseAgent):
    """交付者。"""

    role_type = AgentRole.DELIVERER

    def check_completion(self) -> tuple[bool, list[dict]]:
        """检查所有任务是否完成；返回 (是否全部完成, 未完成任务列表)。"""
        tasks = self.repo.list_tasks(self.project_id)
        incomplete = [
            t for t in tasks
            if t["status"] not in (TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value)
        ]
        return (not incomplete), incomplete

    def collect(self) -> dict:
        """汇总项目交付信息。"""
        project = self.repo.get_project(self.project_id)
        tasks = self.repo.list_tasks(self.project_id)
        agents = self.repo.list_agents(self.project_id)
        artifacts = self.repo.list_artifacts(self.project_id)
        by_id = {a["id"]: a for a in agents}
        art_by_task: dict[int, int] = {}
        for art in artifacts:
            art_by_task[art["task_id"]] = art_by_task.get(art["task_id"], 0) + 1
        for t in tasks:
            t["_assignee"] = by_id.get(t["assignee_id"], {}).get("name", "")
            t["_agents"] = agents
            t["artifact_count"] = art_by_task.get(t["id"], 0)
        return {
            "project_id": self.project_id,
            "project_name": self.ctx.project_name,
            "requirement": project["requirement"],
            "project_status": project["status"],
            "executer_count": sum(1 for a in agents if a["role_type"] == AgentRole.EXECUTER),
            "agents": agents,
            "tasks": tasks,
            "artifacts": artifacts,
        }

    def deliver(self, extra_langs: list[str] | None = None) -> dict:
        """执行交付流程：检查 → 生成 README → 冒烟测试 → 标记完成。"""
        ready, incomplete = self.check_completion()
        meta = self.collect()
        meta["project_status"] = "completed" if ready else "degraded"

        if ready:
            self.ctx.workspace_dir.mkdir(parents=True, exist_ok=True)
            meta["smoke"] = {"status": "IN_PROGRESS", "summary": "冒烟测试执行中"}
            written = write_readmes(self.ctx.workspace_dir, meta, extra_langs)
            meta["readmes"] = [str(w) for w in written]

            smoke = SmokeTester().run(meta, self.ctx.workspace_dir)
            meta["smoke"] = {
                "status": smoke.status,
                "summary": smoke.summary,
                "checks": smoke.checks,
            }
            # 交付（冒烟失败也交付并在报告中标注）
            meta["project_status"] = "delivered"
            # 重写 README，使其包含最终冒烟结果与交付状态
            write_readmes(self.ctx.workspace_dir, meta, extra_langs)
        else:
            meta["incomplete"] = [t["name"] for t in incomplete]
            meta["smoke"] = {"status": "SKIP", "summary": "存在未完成任务，跳过冒烟测试"}

        self.repo.update_project(
            self.project_id,
            status=meta["project_status"],
            result_path=str(self.ctx.workspace_dir),
        )
        meta["result_path"] = str(self.ctx.workspace_dir)
        self.audit("deliver", f"交付完成，状态={meta['project_status']}")
        return meta