"""消息优先级模型与排序。

处理优先级（数值越小越优先）：
1. 私信 —— 按创建时间旧到新
2. 群聊中明确 @ 当前 Agent —— 按创建时间旧到新
3. 已订阅/加入的普通群聊消息 —— 按创建时间旧到新
4. Agent 主动发起的任务检查/协作行为

同优先级严格按 (created_at, id) 升序（旧消息先处理）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from ..storage.repository import Repository


class MessagePriority(IntEnum):
    """数值越小优先级越高。"""

    INBOX = 0  # 保留
    DIRECT = 1  # 私信
    MENTION = 2  # 群聊 @
    GROUP = 3  # 普通群聊
    SELF = 4  # 主动行为


@dataclass(order=True)
class MessageItem:
    """待处理消息条目，支持按 (priority, created_at, id) 排序。"""

    priority: MessagePriority
    sort_key: str = field(init=False)
    id: int
    created_at: str
    kind: str  # dm / group / mention
    msg: dict
    chat_id: int = 0

    def __post_init__(self) -> None:
        # 先按 priority，再按 (created_at, id)
        self.sort_key = f"{int(self.priority):02d}|{self.created_at}|{self.id:010d}"


def resolve_mailbox(
    repo: Repository,
    agent_id: int,
    dm_items: list[MessageItem],
    group_items: list[MessageItem],
) -> list[MessageItem]:
    """把私信与群聊条目合并为全局有序处理队列。

    :param dm_items: 私信条目（DIRECT 优先级）。
    :param group_items: 群聊条目（MENTION/GROUP 优先级）。
    """
    items = sorted(dm_items + group_items, key=lambda it: (int(it.priority), it.created_at, it.id))
    return items


def make_dm_item(msg: dict) -> MessageItem:
    return MessageItem(
        priority=MessagePriority.DIRECT,
        id=msg["id"],
        created_at=msg["created_at"],
        kind="dm",
        msg=msg,
    )


def make_group_item(msg: dict, chat_id: int, mentioned: bool) -> MessageItem:
    return MessageItem(
        priority=MessagePriority.MENTION if mentioned else MessagePriority.GROUP,
        id=msg["id"],
        created_at=msg["created_at"],
        kind="mention" if mentioned else "group",
        msg=msg,
        chat_id=chat_id,
    )