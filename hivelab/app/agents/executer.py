"""执行 Agent：接收任务、产出产物、通过私信/群聊协作、汇报进度。"""

from __future__ import annotations

from pathlib import Path

from ..llm.base import ChatMessage
from ..messaging.priority import MessageItem
from ..tasks.service import TaskStatus
from .runtime import AgentRole, BaseAgent

_REPLY_PROMPT = """你是一位 {role}。对方发来如下消息，请判断是否需要回复；若需要，请用一两句直接答复，保持专业与简洁。

消息：{content}

（若无需回复，请直接回一个空串。）
"""


class ExecuteAgent(BaseAgent):
    """在线执行者，处理一条消息或推进一个任务。"""

    role_type = AgentRole.EXECUTER

    def __init__(self, ctx, name: str, agent_id: int, logger, role: str = "执行") -> None:
        super().__init__(ctx, name, agent_id, logger)
        self._role = role or "执行"
        self._asked_peer = False
        self._artifact_ext = ".txt"

    # ---------- 单步驱动 ----------
    def step(self) -> bool:
        """执行一轮：处理消息，然后推进任务。返回是否有实质进展。"""
        did = False
        if self._process_messages():
            did = True
        if self._work_on_tasks():
            did = True
        return did

    # ---------- 消息处理 ----------
    def _process_messages(self) -> bool:
        queue = self.hub.poll_once(self.agent_id)
        developed = False
        for item in queue:
            decided = self._handle_item(item)
            if item.kind == "dm":
                self.repo.mark_direct_read(item.msg["id"])
            if decided:
                developed = True
        return developed

    def _handle_item(self, item: MessageItem) -> bool:
        reply = self._decide_reply(item.msg)
        sender_id = item.msg["sender_id"]
        if reply:
            if item.kind == "dm":
                self.send_dm(sender_id, reply, needs_reply=0)
            else:
                # 群聊回复不 @ 回对方，避免无限 @ 循环
                self.hub.send_group(item.chat_id, self.agent_id, reply)
            self.audit("msg_reply", f"回复 [{item.kind}] 消息 #{item.msg['id']}: {reply[:120]}", )
            return True
        else:
            self.audit("msg_skip", f"忽略未提问消息 #{item.msg['id']}")
            return False

    def _decide_reply(self, msg: dict) -> str:
        content = msg["content"]
        needs = msg.get("needs_reply", 0) or self._is_question(content)
        if not needs:
            return ""
        try:
            text = self.llm.complete(
                [
                    ChatMessage.system(
                        _REPLY_PROMPT.format(role=self._role, content=content)
                    )
                ]
            )
        except Exception as exc:
            self.log_error("reply", detail=f"回复失败: {exc}", exc=exc)
            return ""
        return text.strip()

    @staticmethod
    def _is_question(text: str) -> bool:
        from .prompts import is_question

        return is_question(text)

    # ---------- 任务推进 ----------
    def work_task_once(self, task: dict) -> bool:
        """针对单个任务做一次推进：开始 or 产出并完成。"""
        status = task["status"]
        tid = task["id"]
        if status in (TaskStatus.PENDING.value, TaskStatus.ASSIGNED.value):
            if not self.tasks.dependencies_ready(tid):
                self.audit("task_wait", f"等待前置任务完成 #{tid}", task_id=tid)
                return False
            self.tasks.start(tid)
            self.audit("task_start", f"开始任务 #{tid} {task['name']}", task_id=tid)
            return True
        if status == TaskStatus.IN_PROGRESS.value:
            artifact = self._produce_artifact(task)
            self.tasks.complete(tid, artifacts=[artifact], progress=f"{task['name']} 已完成")
            self.audit("task_complete", f"完成任务 #{tid}，产物 {artifact}", task_id=tid)
            self._collaborate_once(task)
            return True
        return False

    def _work_on_tasks(self) -> bool:
        developed = False
        for task in self.tasks.repo.list_tasks_by_assignee(self.agent_id):
            if task["status"] in (
                TaskStatus.PENDING.value,
                TaskStatus.ASSIGNED.value,
                TaskStatus.IN_PROGRESS.value,
            ):
                if self.work_task_once(task):
                    developed = True
        return developed

    def _produce_artifact(self, task: dict) -> str:
        """在当前项目目录生成一个产物文件（模拟执行产出）。"""
        self.workspace.mkdir(parents=True, exist_ok=True)
        slug = "".join(ch for ch in task["name"] if ch.isalnum())[:20] or f"task{task['id']}"
        path = self.workspace / f"artifact_{task['id']}_{slug}{self._artifact_ext}"
        content = (
            f"# 产物：{task['name']}\n"
            f"执行 Agent：{self.name}\n"
            f"需求：{self.ctx.requirement}\n"
            f"完成条件：{task['completion_definition']}\n"
            f"本文件为 {self._role} 阶段交付物。\n"
        )
        path.write_text(content, encoding="utf-8")
        self.repo.add_artifact(
            self.project_id, task["id"], self.agent_id,
            str(path), f"{task['name']} 产物",
        )
        return str(path)

    # ---------- 协作 ----------
    def _collaborate_once(self, task: dict) -> None:
        """首次完成任务时，向另一位执行 Agent 发起一次协作提问。"""
        if self._asked_peer:
            return
        peers = [
            a for a in self.repo.list_agents(self.project_id)
            if a["role_type"] == AgentRole.EXECUTER and a["id"] != self.agent_id
        ]
        if not peers or not self.ctx.group_chat_id:
            return
        peer = peers[0]
        question = (
            f"@{peer['name']} 你好，我正在完成「{task['name']}」，"
            f"请问你们的接口地址/返回结构是怎么约定的？我这边需要保持一致。"
        )
        self.send_group(self.ctx.group_chat_id, question, mention_ids=[peer["id"]])
        # 同时发一条私信确保对方收到
        self.send_dm(peer["id"], question, needs_reply=1)
        self._asked_peer = True
        self.audit("collab_ask", f"向 {peer['name']}(#{peer['id']}) 发起协作提问")