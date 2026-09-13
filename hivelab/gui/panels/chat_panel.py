"""聊天面板：查看智体间的群聊与私信协作。"""

from __future__ import annotations

import html as _html

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...web.app import WebService

# 消息徽章配色（低饱和，参考 minimalist 淡马卡龙）
_GROUP_TAG_BG = "#E5EEFB"
_GROUP_TAG_FG = "#2F5B9E"
_DM_TAG_BG = "#E9F2EA"
_DM_TAG_FG = "#33613A"


class ChatPanel(QWidget):
    """以某个智体为视角，展示其参与的群聊与私信消息。"""

    def __init__(self, svc: WebService) -> None:
        super().__init__()
        self.svc = svc
        self._last_payload: str = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        kicker = QLabel("智体协作")
        kicker.setObjectName("moduleKicker")
        root.addWidget(kicker)

        title = QLabel("协作消息流转")
        title.setObjectName("serifTitle")
        root.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("查看智体"))
        self._agent_combo = QComboBox()
        self._agent_combo.addItem("（全部智体）", -1)
        self._agent_combo.currentIndexChanged.connect(lambda *_: self._render())
        row.addWidget(self._agent_combo, 1)
        row.addStretch(1)
        root.addLayout(row)

        self._messages = QTextBrowser()
        self._messages.setOpenExternalLinks(True)
        root.addWidget(self._messages, 1)

        self.refresh()

    def refresh(self) -> None:
        self._load_agents()
        self._render()

    def _load_agents(self) -> None:
        current = self._agent_combo.currentData()
        try:
            agents = self.svc.list_agents()
        except Exception:
            return
        prev = self._agent_combo.blockSignals(True)
        self._agent_combo.clear()
        self._agent_combo.addItem("（全部智体）", -1)
        for a in agents:
            label = f"{a.get('name', '?')}  [{a.get('role_type', '')}]"
            self._agent_combo.addItem(label, a["id"])
        if current is not None:
            idx = self._agent_combo.findData(current)
            if idx >= 0:
                self._agent_combo.setCurrentIndex(idx)
        self._agent_combo.blockSignals(prev)

    def _render(self) -> None:
        try:
            repo = self.svc.orch().repo
            agents = {a["id"]: a for a in repo.list_agents()}
        except Exception:
            return

        selected = self._agent_combo.currentData()
        msgs: list[dict] = []

        # 群聊
        chats = repo.list_group_chats()
        for ch in chats:
            if selected is not None and selected >= 0:
                if not repo.is_group_member(ch["id"], selected):
                    continue
            for m in repo.list_group_messages(ch["id"]):
                msgs.append(
                    {
                        "ts": m.get("created_at", ""),
                        "kind": "group",
                        "chat": ch.get("name", "群聊"),
                        "sender": self._agent_name(agents, m.get("sender_id")),
                        "content": m.get("content", ""),
                    }
                )

        # 私信（该智体收到的）
        if selected is not None and selected >= 0:
            for m in repo.list_direct_messages_for(selected):
                msgs.append(
                    {
                        "ts": m.get("created_at", ""),
                        "kind": "dm",
                        "chat": "私信",
                        "sender": self._agent_name(agents, m.get("sender_id")),
                        "target": self._agent_name(agents, selected),
                        "content": m.get("content", ""),
                    }
                )

        msgs.sort(key=lambda m: m["ts"])
        payload = repr(msgs[-200:])
        if payload == self._last_payload:
            return
        self._last_payload = payload

        if not msgs:
            self._messages.setHtml(
                "<p style='color:#9B968B'>暂无协作消息。启动一个项目后，"
                "智体团队会在群聊与私信中交流。</p>"
            )
            return

        blocks = ["<h3>协作消息流</h3>"]
        for m in msgs[-200:]:
            if m["kind"] == "group":
                tag = (
                    f"<span style='background:{_GROUP_TAG_BG};color:{_GROUP_TAG_FG};"
                    f"padding:1px 8px;border-radius:999px;font-size:12px'>"
                    f"群聊 · {self._e(m['chat'])}</span>"
                )
            else:
                tag = (
                    f"<span style='background:{_DM_TAG_BG};color:{_DM_TAG_FG};"
                    f"padding:1px 8px;border-radius:999px;font-size:12px'>私信</span>"
                )
            blocks.append(
                f"<div style='padding:8px 2px;border-bottom:1px solid #ECE9E4;'>"
                f"<b style='font-size:14px'>{self._e(m.get('sender', '?'))}</b> "
                f"{tag} "
                f"<span style='color:#9B968B;font-size:12px'>{self._e(m.get('ts', ''))}</span><br>"
                f"<span style='font-size:13px;line-height:1.6'>{self._e(m.get('content', ''))}</span>"
                f"</div>"
            )
        self._messages.setHtml("".join(blocks))

    @staticmethod
    def _agent_name(agents: dict, agent_id) -> str:
        a = agents.get(agent_id)
        return a.get("name", f"#{agent_id}") if a else f"#{agent_id}"

    @staticmethod
    def _e(text: str) -> str:
        return _html.escape(text or "").replace("\n", "<br>")