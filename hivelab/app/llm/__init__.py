"""统一模型接口模块。

核心业务代码只依赖 ``LLMClient`` 抽象，不依赖任何具体服务商。
"""

from .base import LLMClient, ChatMessage, LLMClientError
from .mock import MockLLMClient
from .openai import OpenAICompatClient
from .factory import create_client, build_default_client

__all__ = [
    "LLMClient",
    "ChatMessage",
    "LLMClientError",
    "MockLLMClient",
    "OpenAICompatClient",
    "create_client",
    "build_default_client",
]