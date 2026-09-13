"""任务看板面板：按项目查看任务及其派生状态。

设计要点：无 emoji；状态用语义色以“徽章”形式呈现（淡底 + 深字 + 圆形留白）；
表格无网格、行悬停由 QSS 统一处理。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...web.app import WebService
from ..theme import _ST_DONE_BG, _ST_DONE_FG, _ST_FAIL_BG, _ST_FAIL_FG, _ST_NEUTRAL_BG, _ST_NEUTRAL_FG, _ST_RUN_BG, _ST_RUN_FG, _ST_WARN_BG, _ST_WARN_FG

_STATUS_CN = {
    "pending": "待处理",
    "assigned": "已分配",
    "in_progress": "进行中",
    "blocked": "已阻塞",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
}

# 任务状态 → 徽章配色（淡底 + 深字）
_STATUS_BADGE = {
    "completed": (_ST_DONE_BG, _ST_DONE_FG),
    "in_progress": (_ST_RUN_BG, _ST_RUN_FG),
    "assigned": (_ST_RUN_BG, _ST_RUN_FG),
    "failed": (_ST_FAIL_BG, _ST_FAIL_FG),
    "blocked": (_ST_WARN_BG, _ST_WARN_FG),
    "cancelled": (_ST_NEUTRAL_BG, _ST_NEUTRAL_FG),
    "pending": (_ST_NEUTRAL_BG, _ST_NEUTRAL_FG),
}


class TaskPanel(QWidget):
    """以表格展示所选项目的任务看板。"""

    def __init__(self, svc: WebService) -> None:
        super().__init__()
        self.svc = svc

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        kicker = QLabel("任务看板")
        kicker.setObjectName("moduleKicker")
        root.addWidget(kicker)

        title = QLabel("团队分工，一目了然")
        title.setObjectName("serifTitle")
        root.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("项目"))
        self._project_combo = QComboBox()
        self._project_combo.addItem("（全部项目）", -1)
        self._project_combo.currentIndexChanged.connect(lambda *_: self._render())
        row.addWidget(self._project_combo, 1)
        row.addStretch(1)
        root.addLayout(row)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["ID", "任务名称", "负责人", "优先级", "状态", "依赖", "创建时间"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setVisible(False)
        root.addWidget(self._table, 1)

        self.refresh()

    def refresh(self) -> None:
        self._load_projects()
        self._render()

    def _load_projects(self) -> None:
        current = self._project_combo.currentData()
        try:
            projects = self.svc.list_projects()
        except Exception:
            return
        prev = self._project_combo.blockSignals(True)
        self._project_combo.clear()
        self._project_combo.addItem("（全部项目）", -1)
        for p in projects:
            self._project_combo.addItem(
                f"#{p['id']}  {(p.get('requirement') or '').replace(chr(10), ' ')[:20]}", p["id"]
            )
        if current is not None:
            idx = self._project_combo.findData(current)
            if idx >= 0:
                self._project_combo.setCurrentIndex(idx)
        self._project_combo.blockSignals(prev)

    def _render(self) -> None:
        pid = self._project_combo.currentData()
        pid = None if pid == -1 else pid
        try:
            repo = self.svc.orch().repo
            tasks = repo.list_tasks(pid) if pid is not None else self.svc.list_tasks()
            agents = {a["id"]: a for a in repo.list_agents()}
            all_tasks = repo.list_tasks()
            task_map = {t["id"]: t for t in all_tasks}
        except Exception:
            return

        self._table.setRowCount(0)
        for t in tasks:
            row = self._table.rowCount()
            self._table.insertRow(row)

            col_id = QTableWidgetItem(str(t.get("id", "")))
            col_name = QTableWidgetItem(t.get("name", ""))
            assignee = self._agent_name(agents, t.get("assignee_id"))
            col_assignee = QTableWidgetItem(assignee)
            col_prio = QTableWidgetItem(str(t.get("priority", 5)))
            status = t.get("status", "")
            col_status = QTableWidgetItem(_STATUS_CN.get(status, status))

            # 状态徽章：淡底 + 深字，居中
            col_status.setTextAlignment(Qt.AlignCenter)
            bg, fg = _STATUS_BADGE.get(status, (_ST_NEUTRAL_BG, _ST_NEUTRAL_FG))
            col_status.setBackground(QColor(bg))
            col_status.setForeground(QColor(fg))
            col_status.setData(Qt.UserRole, status)

            deps = repo.parse_dependencies(t)
            dep_names = []
            for d in deps:
                dt = task_map.get(d)
                dep_names.append(dt.get("name", "#%d" % d) if dt else "#%d" % d)
            col_dep = QTableWidgetItem(", ".join(dep_names) or "—")
            col_ts = QTableWidgetItem((t.get("created_at") or "")[:19])

            for i, c in enumerate((col_id, col_name, col_assignee, col_prio, col_status, col_dep, col_ts)):
                c.setTextAlignment(Qt.AlignVCenter)
                self._table.setItem(row, i, c)

    @staticmethod
    def _agent_name(agents: dict, agent_id) -> str:
        a = agents.get(agent_id)
        return a.get("name", "未分配") if a else "未分配"