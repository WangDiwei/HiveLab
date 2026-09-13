"""统一配置加载。

设计原则：
- 配置来源优先级：显式传入的 dict > 环境变量 > .env 文件 > 内置默认值。
- API Key 永不写死在源码，仅从配置源读取。
- 支持桌面端把用户填写的配置持久化到用户数据目录（见 persistence.py）。
"""

from __future__ import annotations

import os
from pathlib import Path
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderMode(str, Enum):
    """模型服务商运行模式。"""

    AUTO = "auto"  # 配置了真实模型用真实模型，否则退回 MockLLM
    MOCK = "mock"  # 强制使用内置模拟模型（开发/测试）
    REAL = "real"  # 强制使用真实模型，未配置则报错


class Settings(BaseModel):
    """HiveLab 全局配置。"""

    # --- LLM ---
    llm_api_base: str = Field(default="https://api.openai.com/v1", alias="LLM_API_BASE")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_timeout: int = Field(default=120, alias="LLM_TIMEOUT")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, alias="LLM_MAX_TOKENS")
    llm_stream: bool = Field(default=False, alias="LLM_STREAM")
    llm_provider: ProviderMode = Field(default=ProviderMode.AUTO, alias="LLM_PROVIDER")
    mock_provider: bool = Field(default=True, alias="MOCK_PROVIDER")

    # --- 协作 ---
    group_chat_poll_interval: int = Field(default=60, alias="GROUP_CHAT_POLL_INTERVAL")

    # --- 存储 ---
    db_path: str = Field(default="", alias="DB_PATH")

    # --- 工作区 ---
    workspace_root: str = Field(default="", alias="WORKSPACE_ROOT")

    model_config = {"populate_by_name": True, "validate_assignment": True}

    # ---- 便捷派生属性 ----
    @property
    def resolve_db_path(self) -> Path:
        """返回数据库文件路径，默认位于用户数据目录。"""
        if self.db_path:
            return Path(self.db_path).expanduser()
        data_dir = Path(os.environ.get("LOCALAPPDATA", "~/.hivelab"))
        data_dir = Path(data_dir).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "hivelab.db"

    @property
    def resolve_workspace_root(self) -> Path:
        """返回工作区根目录。"""
        if self.workspace_root:
            return Path(self.workspace_root).expanduser()
        base = Path(os.environ.get("LOCALAPPDATA", "~/.hivelab"))
        root = Path(base).expanduser() / "HiveLabProjects"
        root.mkdir(parents=True, exist_ok=True)
        return root


def load_settings(
    env_file: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> Settings:
    """加载全局配置。

    :param env_file: 可选的自定义 .env 文件路径。
    :param overrides: 直接覆盖的配置项（优先级最高），key 为字段名或别名。
    """
    values: dict[str, Any] = {}

    # 1) 从 .env 文件读取（若存在）
    if env_file is not None:
        values.update(_read_dotenv(Path(env_file)))
    else:
        values.update(_read_dotenv(_default_env_file()))

    # 2) 从真实环境变量读取
    values.update(_read_env())

    if not env_file and not values:
        settings = Settings()
    else:
        settings = Settings(**values)

    # 3) 显式覆盖（最高优先级）：按字段名或别名匹配后直接赋值，避免别名/字段名冲突
    if overrides:
        for key, val in overrides.items():
            field = Settings.model_fields.get(key) or Settings.model_fields.get(key.lower())
            if field is None:
                # 尝试以别名匹配
                field = next(
                    (f for f in Settings.model_fields.values() if (f.alias or "").lower() == key.lower()),
                    None,
                )
            if field is not None:
                setattr(settings, field_name_of(field) or key, val)
    return settings


def field_name_of(field) -> str | None:
    """根据字段值反查 pydantic 字段名（内部工具）。"""
    for name, f in Settings.model_fields.items():
        if f is field:
            return name
    return None


def _default_env_file() -> Path:
    """从当前目录或项目根目录寻找 .env。"""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[3] / ".env",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def _read_dotenv(path: Path) -> dict[str, str]:
    """轻量读取 .env（不依赖 python-dotenv，便于测试）。"""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    try:
        from dotenv import dotenv_values

        result = dotenv_values(str(path))
    except ImportError:  # pragma: no cover - 纯兜底
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip().strip('"').strip("'")
    return {k: v for k, v in result.items() if v != ""}


def _read_env() -> dict[str, str]:
    """读取与配置项同名的大写环境变量。"""
    mapping: dict[str, str] = {}
    for f in Settings.model_fields.keys():
        alias = Settings.model_fields[f].alias or f
        env_alias = alias.upper()
        val = os.environ.get(env_alias)
        if val is not None and val != "":
            mapping[alias] = val
    return mapping