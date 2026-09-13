"""用户配置持久化。

桌面端让普通用户在首次运行时填写模型服务商配置，然后持久化到本地，
避免每次都要输入，也避免把 Key 写死在源码/程序包中。

文件位置：用户数据目录（Windows 为 %LOCALAPPDATA%/HiveLab/config.json）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .settings import Settings


def _config_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".hivelab")
    return Path(base) / "HiveLab" / "config.json"


_PERSIST_KEYS = [
    "llm_api_base",
    "llm_api_key",
    "llm_model",
    "llm_timeout",
    "llm_max_retries",
    "llm_temperature",
    "llm_max_tokens",
    "llm_stream",
    "llm_provider",
    "group_chat_poll_interval",
]


def save_settings(settings: Settings | dict[str, Any]) -> Path:
    """把当前配置持久化到磁盘。返回保存路径。"""
    if isinstance(settings, Settings):
        data = {k: getattr(settings, k, None) for k in _PERSIST_KEYS}
    else:
        data = {k: settings.get(k) for k in _PERSIST_KEYS}
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_settings_file() -> dict[str, Any]:
    """读取持久化的用户配置；不存在则返回空字典。"""
    path = _config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def apply_user_settings(settings: Settings | None = None) -> Settings:
    """把持久化的用户配置合并进 Settings 返回。"""
    user = load_settings_file()
    if not user:
        return settings or Settings()
    if settings is None:
        return Settings(**{k: v for k, v in user.items() if v is not None})
    for k, v in user.items():
        if v is not None and k in Settings.model_fields:
            setattr(settings, k, v)
    return settings


def has_configured_model(settings: Settings | None = None) -> bool:
    """是否已配置可用于真实调用的模型服务商。"""
    s = settings or apply_user_settings()
    return bool(s.llm_api_base and s.llm_api_key and s.llm_model)