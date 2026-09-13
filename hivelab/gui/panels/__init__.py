"""桌面应用各个面板。"""

from .chat_panel import ChatPanel
from .log_panel import LogPanel
from .requirement_panel import RequirementPanel
from .settings_panel import SettingsPanel
from .task_panel import TaskPanel

__all__ = [
    "ChatPanel",
    "LogPanel",
    "RequirementPanel",
    "SettingsPanel",
    "TaskPanel",
]