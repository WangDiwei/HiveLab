"""规划者 Agent：分析需求、拆解任务、命名/创建执行 Agent、分配并调度。"""

from __future__ import annotations

import json
from typing import Any

from ..llm.base import ChatMessage
from .runtime import AgentRole, BaseAgent
from .prompts import extract_json

_PLAN_PROMPT = """你是一位资深项目规划者。请把用户的下列需求拆解为可执行任务计划。

要求：
1. 用 JSON 数组返回，每个元素代表一个任务，包含字段：
   - name: 任务名（简短）
   - description: 任务描述
   - role: 负责该任务的角色（如 前端/后端/数据库/测试/文档/其他）
   - assignee: 分配的执行 Agent 名称（请起易懂名字，如 "前端 Agent"、"后端 Agent"）
   - priority: 优先级整数（1 最高，9 最低）
   - dependencies: 前置任务在下标数组中的索引列表[]
   - completion_definition: 完成条件
2. assignee 名称请保持统一（同名任务应同上一个 Agent 完成）。
3. dependencies 用任务在数组中的下标表示。

用户需求：
{requirement}
"""

DEFAULT_FALLBACK_TEAMS = [
    ("需求分析与界面", "前端 Agent", "前端", 1, []),
    ("业务逻辑与数据", "后端 Agent", "后端", 2, [0]),
    ("测试与联调", "测试 Agent", "测试", 3, [1]),
]


class PlannerAgent(BaseAgent):
    """规划者。"""

    role_type = AgentRole.PLANNER

    # ---- 任务拆解 ----
    def build_plan(self) -> dict[str, Any]:
        """分析需求并产出任务计划（含 agent 命名与依赖）。失败时回退到默认拆解。"""
        out = {}
        try:
            text = self.llm.complete(
                [ChatMessage.system(_PLAN_PROMPT.format(requirement=self.ctx.requirement))]
            )
        except Exception as exc:
            self.log_error("analyze", detail=f"规划 LLM 调用失败，使用默认拆解: {exc}", exc=exc)
            out["plan"] = self._fallback_plan()
            out["fallback"] = True
            return out

        data = extract_json(text)
        tasks = self._normalize_tasks(data)
        if not tasks:
            self.audit("plan_fallback", "LLM 输出无法解析为任务计划", )
            out["plan"] = self._fallback_plan()
            out["fallback"] = True
            return out
        out["plan"] = tasks
        out["fallback"] = False
        return out

    def _fallback_plan(self) -> list[dict[str, Any]]:
        """确定性兜底拆解：至少生成 3 个任务、2 个 Agent，保证可端到端运行。"""
        tasks: list[dict[str, Any]] = []
        for idx, (name, agent_name, role, priority, deps) in enumerate(
            DEFAULT_FALLBACK_TEAMS
        ):
            tasks.append(
                {
                    "name": f"{name}",
                    "description": f"针对需求「{self.ctx.requirement}」完成{name}工作。",
                    "role": role,
                    "assignee": agent_name,
                    "priority": priority,
                    "dependencies": deps,
                    "completion_definition": f"{name}交付物已生成",
                }
            )
        return tasks

    @staticmethod
    def _normalize_tasks(data: dict | None) -> list[dict[str, Any]]:
        if not data or not isinstance(data, dict):
            return []
        raw = data.get("tasks", data)
        if isinstance(raw, dict):
            raw = raw.get("tasks", [])
        if not isinstance(raw, list):
            return []
        normalized = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "name": str(item.get("name", "")).strip() or "未命名任务",
                    "description": str(item.get("description", "")).strip(),
                    "role": str(item.get("role", "其他")),
                    "assignee": str(item.get("assignee", "执行 Agent")).strip()
                    or "执行 Agent",
                    "priority": int(item.get("priority", 5) or 5),
                    "dependencies": [
                        int(d) for d in (item.get("dependencies") or [])
                    ],
                    "completion_definition": str(
                        item.get("completion_definition", "")
                    ),
                }
            )
        return normalized

    # ---- 落地执行 ----
    def plan_and_spawn(self) -> list[dict[str, Any]]:
        """拆解需求 → 创建/复用执行 Agent → 建任务 → 分配 → 拉群。

        返回 [(task_row, agent_row), ...]
        """
        self.repo.update_project(self.project_id, status="planning")
        result = self.build_plan()
        tasks_plan = result["plan"] if "plan" in result else self.build_plan()["plan"]
        if "fallback" in result:
            self.audit("plan_fallback", "使用默认任务拆解")

        # Agent 名称 -> agent_id
        agent_map: dict[str, int] = {}
        assignments: list[tuple[int, int]] = []  # (task_id, agent_id)
        created_tasks: list[dict[str, Any]] = []

        for item in tasks_plan:
            agent_name = item["assignee"]
            if agent_name not in agent_map:
                existing = self.repo.find_agent_by_name(agent_name, self.project_id)
                if existing:
                    aid = existing["id"]
                else:
                    aid = self.repo.create_agent(
                        agent_name, AgentRole.EXECUTER, self.project_id,
                        description=f"负责：{item['role']}",
                    )
                agent_map[agent_name] = aid

        for item in tasks_plan:
            deps = [created_tasks[i]["id"] for i in item["dependencies"] if i < len(created_tasks)]
            tid = self.tasks.create_task(
                project_id=self.project_id,
                name=item["name"],
                description=item["description"],
                creator_id=self.agent_id,
                assignee_id=agent_map[item["assignee"]],
                priority=item["priority"],
                dependencies=deps,
                completion_definition=item["completion_definition"],
            )
            self.tasks.assign(tid, agent_map[item["assignee"]])
            created_tasks.append(self.tasks.get_task(tid))
            assignments.append((tid, agent_map[item["assignee"]]))

        self.audit("plan_executed", f"创建 {len(created_tasks)} 个任务、{len(agent_map)} 个执行 Agent")
        return assignments

    def create_collab_group(self, deliverer_id: int = 0) -> int:
        """创建项目协作群并邀请所有执行 Agent + 交付者。"""
        chat = self.hub.create_group("项目协作群", creator_id=self.agent_id, project_id=self.project_id)
        for agent in self.repo.list_agents(self.project_id):
            if agent["role_type"] == AgentRole.EXECUTER:
                self.hub.join_group(chat, agent["id"])
        if deliverer_id:
            self.hub.join_group(chat, deliverer_id)
        self.ctx.group_chat_id = chat
        self.audit("open_group", f"创建协作群 #{chat}")
        return chat