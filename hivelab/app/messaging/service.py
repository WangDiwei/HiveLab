"""消息中心：封装发送/接收与轮询，持有每个 Agent 的群聊已读游标。"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..storage.repository import Repository
from .priority import (
    MessageItem,
    resolve_mailbox,
    make_dm_item,
    make_group_item,
)


@dataclass
class _Cursor:
    """记录每个 Agent 在每个群聊的最新已读消息 id 与最新 @ 消息 id。"""

    last_read: int = 0
    last_mention_read: int = 0


class MessageHub:
    """提供私信/群聊的发送与（面向单个 Agent 的）消息轮询接口。

    所有消息都持久化到数据库；各 Agent 的已读游标仅保存在内存中
    （由协作运行时持有，便于可替换为事件驱动）。
    """

    def __init__(self, repo: Repository) -> None:
        self._repo = repo
        # agent_id -> chat_id -> cursor
        self._cursors: dict[int, dict[int, _Cursor]] = {}

    @property
    def repo(self) -> Repository:
        return self._repo

    # ---------- 发送 ----------
    def send_dm(
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
        return self._repo.send_direct_message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            project_id=project_id,
            priority=priority,
            needs_reply=needs_reply,
            reply_to_id=reply_to_id,
        )

    def create_group(self, name: str, creator_id: int, project_id: int = 0) -> int:
        return self._repo.create_group_chat(name, creator_id, project_id)

    def join_group(self, chat_id: int, agent_id: int) -> None:
        self._repo.add_group_member(chat_id, agent_id)
        self._cursors.setdefault(agent_id, {}).setdefault(chat_id, _Cursor())

    def leave_group(self, chat_id: int, agent_id: int) -> None:
        self._repo.remove_group_member(chat_id, agent_id)
        self._cursors.get(agent_id, {}).pop(chat_id, None)

    def invite(self, chat_id: int, agent_id: int) -> None:
        """创建者邀请其他 Agent 加入群聊。"""
        self.join_group(chat_id, agent_id)

    def send_group(
        self, chat_id: int, sender_id: int, content: str, mention_ids: list[int] | None = None
    ) -> int:
        return self._repo.send_group_message(chat_id, sender_id, content, mention_ids)

    # ---------- 主动查询 ----------
    def history_dm(self, a: int, b: int, limit: int = 200) -> list[dict]:
        return self._repo.list_direct_messages_between(a, b, limit)

    def history_group(self, chat_id: int, after_id: int = 0, limit: int = 500) -> list[dict]:
        return self._repo.list_group_messages(chat_id, after_id, limit)

    def members(self, chat_id: int) -> list[dict]:
        return self._repo.list_group_members(chat_id)

    def chats_of(self, agent_id: int) -> list[dict]:
        return self._repo.list_group_chats_for(agent_id)

    # ---------- 轮询 ----------
    def poll_once(
        self, agent_id: int, explicit_chat_ids: list[int] | None = None
    ) -> list[MessageItem]:
        """返回该 Agent 尚未处理的最优消息队列（按优先级排序）。

        :param explicit_chat_ids: 可选，手动指定要轮询的群聊集合；缺省取该 Agent 已加入的群聊。
        """
        # 1) 未读私信
        dm_msgs = self._repo.list_direct_messages_for(agent_id, unread_only=True)
        dm_items = [make_dm_item(m) for m in dm_msgs]

        # 2) 群聊
        if explicit_chat_ids is not None:
            chat_ids = explicit_chat_ids
        else:
            chat_ids = [c["id"] for c in self._repo.list_group_chats_for(agent_id)]

        group_items: list[MessageItem] = []
        for chat_id in chat_ids:
            cursor = self._cursors.setdefault(agent_id, {}).setdefault(chat_id, _Cursor())
            normal = self._repo.list_group_messages(chat_id, after_id=cursor.last_read)
            mentions = self._repo.list_group_messages_mentioning(
                chat_id, agent_id, after_id=cursor.last_mention_read
            )
            mention_ids = {m["id"] for m in mentions}

            # 推进 @ 游标（@消息需高优先级处理）
            if mentions:
                cursor.last_mention_read = max(m["id"] for m in mentions)

            for m in normal:
                if m["sender_id"] == agent_id:
                    # 跳过自己发的消息
                    continue
                mentioned = m["id"] in mention_ids
                item = make_group_item(m, chat_id, mentioned)
                # 已在 mention 列表中的消息如需高优先级处理也计入；普通游标随后推进
                group_items.append(item)
            if normal:
                cursor.last_read = max(m["id"] for m in normal)

        return resolve_mailbox(self._repo, agent_id, dm_items, group_items)

    def reset_cursor(self, agent_id: int, chat_id: int) -> None:
        """重置某 Agent 在某群聊的已读游标（用于测试/人工介入）。"""
        self._cursors.setdefault(agent_id, {}).pop(chat_id, None)