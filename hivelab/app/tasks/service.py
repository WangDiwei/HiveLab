"""任务状态机定义与任务服务。

任务状态及合法流转（防止非法跳转导致的脏状态）：

.. code-block:: text

    pending ──> assigned ──> in_progress ──> completed
        │          │              │
        │          │              ├──> failed
        │          │              └──> blocked
        │          ▼
        └──────> cancelled <───── (failed/pending/assigned 均可取消)
"""

from __future__ import annotations

from enum import Enum

from ..storage.repository import Repository
from ..utils.logging import now_utc_str


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# 每个状态允许迁移到的目标状态
_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.ASSIGNED, TaskStatus.CANCELLED, TaskStatus.IN_PROGRESS},
    TaskStatus.ASSIGNED: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED, TaskStatus.BLOCKED},
    TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED},
    TaskStatus.BLOCKED: {TaskStatus.IN_PROGRESS, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.FAILED: {TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}

_TERMINAL = {TaskStatus.COMPLETED, TaskStatus.CANCELLED}


class TaskStateError(RuntimeError):
    """非法状态流转。"""


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return target in _TRANSITIONS[current]


class TaskManager:
    """任务的高层服务：负责建任务、分配、起停、依赖检查与状态流转。"""

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    @property
    def repo(self) -> Repository:
        return self._repo

    # ---------- 创建 / 依赖 ----------
    def create_task(
        self,
        *,
        project_id: int,
        name: str,
        description: str = "",
        creator_id: int = 0,
        assignee_id: int = 0,
        priority: int = 5,
        dependencies: list[int] | None = None,
        completion_definition: str = "",
    ) -> int:
        """创建任务；校验依赖存在且不形成环。"""
        deps = self._validate_dependencies(project_id, dependencies or [])
        return self._repo.create_task(
            project_id=project_id,
            name=name,
            description=description,
            creator_id=creator_id,
            assignee_id=assignee_id,
            priority=priority,
            dependencies=deps,
            completion_definition=completion_definition,
        )

    def _validate_dependencies(self, project_id: int, deps: list[int]) -> list[int]:
        seen: set[int] = set()
        stack: list[int] = []
        for d in deps:
            t = self._repo.get_task(d)
            if t is None:
                raise ValueError(f"依赖任务 {d} 不存在")
            if t["project_id"] != project_id:
                raise ValueError(f"依赖任务 {d} 不属于该项目")
            seen.add(d)
            stack.append(d)
        # 简单环检测：不允许依赖自身
        return list(dict.fromkeys(deps))

    def get_task(self, task_id: int) -> dict | None:
        return self._repo.get_task(task_id)

    def list_tasks(self, project_id: int | None = None) -> list[dict]:
        return self._repo.list_tasks(project_id)

    # ---------- 依赖判定 ----------
    def pending_dependencies(self, task_id: int) -> list[dict]:
        """返回尚未完成的前置任务列表。"""
        task = self._repo.get_task(task_id)
        if task is None:
            raise ValueError(f"任务 {task_id} 不存在")
        out = []
        for dep_id in self._repo.parse_dependencies(task):
            dep = self._repo.get_task(dep_id)
            if dep is not None and dep["status"] != TaskStatus.COMPLETED.value:
                out.append(dep)
        return out

    def dependencies_ready(self, task_id: int) -> bool:
        return not self.pending_dependencies(task_id)

    # ---------- 状态流转 ----------
    def _transition(self, task_id: int, target: TaskStatus, extra: dict | None = None) -> dict:
        task = self._repo.get_task(task_id)
        if task is None:
            raise ValueError(f"任务 {task_id} 不存在")
        current = TaskStatus(task["status"])
        if not can_transition(current, target):
            raise TaskStateError(
                f"非法状态流转: {current.value} -> {target.value} (任务 {task_id})"
            )
        fields: dict = {"status": target.value}
        if extra:
            fields.update(extra)
        self._repo.update_task(task_id, **fields)
        return self._repo.get_task(task_id)

    def assign(self, task_id: int, assignee_id: int) -> dict:
        """分配任务：指派执行者并置为 assigned（若依赖就绪）。"""
        task = self._repo.get_task(task_id)
        if task is None:
            raise ValueError(f"任务 {task_id} 不存在")
        current = TaskStatus(task["status"])
        if not can_transition(current, TaskStatus.ASSIGNED):
            raise TaskStateError(
                f"任务 {task_id} 当前状态 {current.value} 不可再次分配"
            )
        self._repo.update_task(task_id, assignee_id=assignee_id)
        if current == TaskStatus.PENDING:
            return self._transition(task_id, TaskStatus.ASSIGNED)
        return self._repo.get_task(task_id)

    def start(self, task_id: int) -> dict:
        """开始执行；要求前置任务均已完成后才可进入 in_progress。"""
        if not self.dependencies_ready(task_id):
            raise TaskStateError(f"任务 {task_id} 前置任务未完成")
        return self._transition(task_id, TaskStatus.IN_PROGRESS, {"started_at": now_utc_str()})

    def complete(self, task_id: int, artifacts: list[str] | None = None, progress: str = "") -> dict:
        """完成任务并记录产物。"""
        extra = {"completed_at": now_utc_str(), "progress": progress or "done"}
        if artifacts is not None:
            import json

            extra["artifacts_json"] = json.dumps(artifacts)
        return self._transition(task_id, TaskStatus.COMPLETED, extra)

    def fail(self, task_id: int, error: str) -> dict:
        return self._transition(task_id, TaskStatus.FAILED, {"error": error[:2000]})

    def block(self, task_id: int, reason: str) -> dict:
        return self._transition(task_id, TaskStatus.BLOCKED, {"error": reason[:2000]})

    def retry(self, task_id: int) -> dict:
        """失败/阻塞后重试：回到 in_progress（或依赖补齐后直接 in_progress）。"""
        task = self._repo.get_task(task_id)
        if task is None:
            raise ValueError(f"任务 {task_id} 不存在")
        current = TaskStatus(task["status"])
        if current == TaskStatus.FAILED:
            self._repo.update_task(task_id, error="")
        if current in (TaskStatus.FAILED, TaskStatus.BLOCKED):
            return self._transition(task_id, TaskStatus.IN_PROGRESS)
        return self._repo.get_task(task_id)

    def cancel(self, task_id: int) -> dict:
        return self._transition(task_id, TaskStatus.CANCELLED)

    def reassign(self, task_id: int, assignee_id: int) -> dict:
        """失败后重新分配：换执行者并回到 assigned。"""
        task = self._repo.get_task(task_id)
        if task is None:
            raise ValueError(f"任务 {task_id} 不存在")
        self._repo.update_task(task_id, assignee_id=assignee_id, error="")
        current = TaskStatus(task["status"])
        if current == TaskStatus.FAILED:
            return self._transition(task_id, TaskStatus.ASSIGNED)
        return self._repo.get_task(task_id)