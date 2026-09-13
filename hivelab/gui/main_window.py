"""HiveLab 主窗口：左侧导航 + 右侧面板。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..web.app import WebService
from .panels.chat_panel import ChatPanel
from .panels.log_panel import LogPanel
from .panels.requirement_panel import RequirementPanel
from .panels.settings_panel import SettingsPanel
from .panels.task_panel import TaskPanel
from .theme import _status_qss, build_stylesheet

_POLL_MS = 2000


class MainWindow(QMainWindow):
    """桌面主界面。"""

    def __init__(self, svc: WebService) -> None:
        super().__init__()
        self.svc = svc

        self.setWindowTitle("HiveLab 多智体协作平台")
        self.resize(1120, 720)

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- 左侧导航 ----
        nav_wrap = QWidget()
        nav_wrap.setFixedWidth(212)
        nav_wrap.setObjectName("navWrap")
        nav_col = QVBoxLayout(nav_wrap)
        nav_col.setContentsMargins(14, 20, 14, 16)
        nav_col.setSpacing(14)

        # 品牌区
        brand = QWidget()
        brand_row = QHBoxLayout(brand)
        brand_row.setContentsMargins(8, 0, 8, 0)
        brand_row.setSpacing(8)
        dot = QLabel("◆")
        dot.setObjectName("brand")
        dot.setFixedSize(22, 22)
        dot.setAlignment(Qt.AlignCenter)
        name = QLabel("HiveLab")
        name.setObjectName("brandName")
        brand_row.addWidget(dot)
        brand_row.addWidget(name)
        brand_row.addStretch(1)
        nav_col.addWidget(brand)

        self._nav = QListWidget()
        self._nav.setObjectName("navList")
        self._nav.setWordWrap(True)
        self._nav.setCurrentRow(0)
        items = [
            ("需求 · 项目", "requirement"),
            ("智体聊天", "chat"),
            ("任务看板", "tasks"),
            ("运行日志", "logs"),
            ("模型配置", "settings"),
        ]
        self._nav_ids: list[str] = []
        for label, key in items:
            it = QListWidgetItem(label)
            it.setSizeHint(it.sizeHint() + QSize(0, 40))
            it.setData(Qt.UserRole, key)
            self._nav.addItem(it)
            self._nav_ids.append(key)
        self._nav.currentRowChanged.connect(self._on_nav)
        nav_col.addWidget(self._nav, 1)

        # 底部版本
        ver = QLabel("HiveLab 0.1.0")
        ver.setObjectName("muted")
        ver.setAlignment(Qt.AlignLeft)
        ver.setContentsMargins(8, 0, 0, 0)
        nav_col.addWidget(ver)

        layout.addWidget(nav_wrap)

        # ---- 右侧面板 ----
        self._stack = QStackedWidget()
        self._requirement = RequirementPanel(svc)
        self._chat = ChatPanel(svc)
        self._tasks = TaskPanel(svc)
        self._logs = LogPanel(svc)
        self._settings = SettingsPanel(svc)

        for w in (self._requirement, self._chat, self._tasks, self._logs, self._settings):
            self._stack.addWidget(w)
        layout.addWidget(self._stack, 1)

        # 定时刷新运行中的项目
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(_POLL_MS)

        self._apply_styles()

    # ---- 导航 ----
    def _on_nav(self, row: int) -> None:
        key = self._nav_ids[row] if 0 <= row < len(self._nav_ids) else None
        mapping = {
            "requirement": 0,
            "chat": 1,
            "tasks": 2,
            "logs": 3,
            "settings": 4,
        }
        if key in mapping:
            self._stack.setCurrentIndex(mapping[key])
            self._refresh_current()

    def goto_settings_panel(self) -> None:
        idx = self._nav_ids.index("settings")
        self._nav.setCurrentRow(idx)
        QMessageBox.information(
            self,
            "欢迎使用 HiveLab",
            "开始前请先在“模型配置”页填写你的 AI 服务商信息。\n"
            "若暂不配置，应用将用内置模拟模式演示完整流程。",
        )
        self._stack.setCurrentIndex(4)

    # ---- 轮询 ----
    def _poll(self) -> None:
        # 运行中的项目在变化时刷新需求页；其余按需刷新
        self._refresh_current()

    def _refresh_current(self) -> None:
        w = self._stack.currentWidget()
        if w is not None:
            w.refresh()

    # ---- 样式 ----
    def _apply_styles(self) -> None:
        self.setStyleSheet(build_stylesheet())