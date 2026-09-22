"""用户配置持久化。

桌面端让普通用户在首次运行时填写模型服务商配置，然后持久化到本地，
避免每次都要输入，也避免把 Key 写死在源码/程序包中。

安全说明：
- 敏感凭据（API Key）**不再写入明文 JSON**，而是存入操作系统密钥环
  （Windows 凭据管理器 / macOS Keychain / Linux SecretService），通过 keyring 库访问。
- 非敏感配置仍保存在用户数据目录的 config.json
  （Windows 为 %LOCALAPPDATA%/HiveLab/config.json）。
- 若密钥环不可用，保存会显式报错，绝不静默退回明文存储。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .settings import Settings

# 敏感字段：存入 OS 密钥环，绝不写入 config.json
_SECRET_KEYS = ["llm_api_key"]
_KEYRING_SERVICE = "HiveLab"

# 非敏感字段：明文存入 config.json
_PERSIST_KEYS = [
    "llm_api_base",
    "llm_model",
    "llm_timeout",
    "llm_max_retries",
    "llm_temperature",
    "llm_max_tokens",
    "llm_stream",
    "llm_provider",
    "group_chat_poll_interval",
]


class KeyringUnavailableError(RuntimeError):
    """密钥环不可用（未安装 keyring，或系统没有可用的后端）。"""


def _config_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".hivelab")
    return Path(base) / "HiveLab" / "config.json"


def _keyring():
    """惰性导入 keyring 并校验后端可用；不可用时抛 KeyringUnavailableError。"""
    try:
        import keyring
    except ImportError as e:  # pragma: no cover - 取决于运行环境
        raise KeyringUnavailableError(
            "未安装 keyring 库，无法安全保存 API Key。请先执行：pip install keyring"
        ) from e

    module = type(keyring.get_keyring()).__module__
    if module.startswith("keyring.backends.fail") or module.startswith("keyring.backends.null"):
        raise KeyringUnavailableError(
            "系统未检测到可用的密钥环后端（如 GNOME Keyring / KWallet / "
            "Windows 凭据管理器 / macOS Keychain），无法安全保存 API Key。"
        )
    return keyring


def _store_secret(name: str, value: str) -> None:
    _keyring().set_password(_KEYRING_SERVICE, name, value)


def _read_secret(name: str) -> str | None:
    try:
        return _keyring().get_password(_KEYRING_SERVICE, name)
    except KeyringUnavailableError:
        return None
    except Exception:  # pragma: no cover - 后端异常兜底
        return None


def _delete_secret(name: str) -> None:
    try:
        _keyring().delete_password(_KEYRING_SERVICE, name)
    except Exception:  # 不存在或后端不可用时无需处理
        pass


def _split(settings: Settings | dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """拆分为 (非敏感字段, 敏感字段)。"""
    if isinstance(settings, Settings):
        data = {k: getattr(settings, k, None) for k in _PERSIST_KEYS}
        secrets = {k: getattr(settings, k, None) for k in _SECRET_KEYS}
    else:
        data = {k: settings.get(k) for k in _PERSIST_KEYS}
        secrets = {k: settings.get(k) for k in _SECRET_KEYS}
    return data, secrets


def _migrate_plaintext_secrets(data: dict[str, Any], path: Path) -> dict[str, Any]:
    """把老版本残留在 config.json 里的明文密钥迁移进密钥环，并从文件抹除。"""
    leaked = {k: data.pop(k) for k in _SECRET_KEYS if k in data}
    if not leaked:
        return data
    try:
        for k, v in leaked.items():
            if v:
                _store_secret(k, str(v))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except KeyringUnavailableError:
        # 无法安全落盘，则仅在内存中保留供本次会话使用（不写回文件）
        data.update(leaked)
    return data


def save_settings(settings: Settings | dict[str, Any]) -> Path:
    """持久化配置：敏感字段进密钥环，非敏感字段进 config.json。返回文件路径。

    若存在需要保存的密钥但密钥环不可用，抛 KeyringUnavailableError（不写明文）。
    """
    data, secrets = _split(settings)

    for k, v in secrets.items():
        if v:
            _store_secret(k, str(v))
        else:
            _delete_secret(k)

    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_settings_file() -> dict[str, Any]:
    """读取持久化的用户配置（合并密钥环中的敏感字段）；不存在则返回空字典。"""
    path = _config_path()
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        data = _migrate_plaintext_secrets(data, path)

    for k in _SECRET_KEYS:
        val = _read_secret(k)
        if val:
            data[k] = val
    return data


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
