"""HiveLab 桌面应用（PySide6）。

普通用户无需安装 Python/依赖：用 PyInstaller 打成单 EXE，
再用 Inno Setup 封装为 MSI 安装包，Win10/Win11 双击即可使用。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..app.config import Settings, load_settings
from ..app.config.persistence import apply_user_settings, has_configured_model
from ..web.app import WebService


def run() -> int:
    """启动桌面应用主界面。"""
    # 延迟导入，避免无图形环境下导入即报错
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow

    settings = apply_user_settings(load_settings())
    svc = WebService(settings)

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("HiveLab")
    app.setOrganizationName("HiveLab")

    win = MainWindow(svc)
    win.show()

    # 首次启动若未配置模型，自动引导到模型配置页
    if not has_configured_model(settings):
        win.goto_settings_panel()

    return app.exec()


def create_service(settings: Settings | None = None) -> WebService:
    """供单测/嵌入使用：构建服务实例。"""
    settings = settings or apply_user_settings(load_settings())
    return WebService(settings)