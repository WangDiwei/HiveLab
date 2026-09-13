"""运行日志面板：查看系统事件与错误。"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...web.app import WebService

# 错误级别 → 前景色
_LEVEL_FG = {
    "error": "#9C3D38",
    "critical": "#b3261e",
    "warning": "#8A6508",
    "info": "#2F5B9E",
}


class LogPanel(QWidget):
    """以表格展示系统事件与错误日志，便于普通人直观了解运行情况。"""

    def __init__(self, svc: WebService) -> None:
        super().__init__()
        self.svc = svc

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        kicker = QLabel("运行日志")
        kicker.setObjectName("moduleKicker")
        root.addWidget(kicker)

        title = QLabel("系统足迹，随时回溯")
        title.setObjectName("serifTitle")
        root.addWidget(title)

        self._tabs = QTabWidget()
        self._event_table = self._make_table(["时间", "模块", "智体", "内容"])
        self._error_table = self._make_table(["时间", "级别", "模块", "智体", "消息"])
        self._tabs.addTab(self._event_table, "系统事件")
        self._tabs.addTab(self._error_table, "错误日志")
        root.addWidget(self._tabs, 1)

        self.refresh()

    @staticmethod
    def _make_table(headers: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.verticalHeader().setVisible(False)
        return t

    def refresh(self) -> None:
        try:
            events = self.svc.list_logs(limit=200)
            errors = self.svc.list_errors(limit=200)
        except Exception:
            return

        self._fill(self._event_table, [["事件"]], events,
                   ["created_at", "module", "agent_name", "content"], 3, level_col=-1)
        self._fill(self._error_table, [], errors,
                   ["created_at", "level", "module", "agent_name", "message"], 4, level_col=1)

    def _fill(self, table: QTableWidget, base: list, rows: list, keys: list,
              content_idx: int, level_col: int = -1) -> None:
        table.setRowCount(0)
        for r in rows:
            row = table.rowCount()
            table.insertRow(row)
            for i, k in enumerate(keys):
                val = r.get(k, "") if isinstance(r, dict) else ""
                if isinstance(val, str) and k == "created_at":
                    val = val[:19]
                item = QTableWidgetItem(str(val))
                if i == content_idx:
                    item.setToolTip(str(val))
                if i == level_col:
                    item.setForeground(QColor(_LEVEL_FG.get(str(val).lower(), "#5C574E")))
                table.setItem(row, i, item)