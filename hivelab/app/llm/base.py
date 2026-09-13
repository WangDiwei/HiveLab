"""统一 LLM 客户端抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Protocol

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """一条对话消息，role 为 system/user/assistant。"""

    role: str
    content: str

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "ChatMessage":
        return cls(role="assistant", content=content)


class LLMClientError(RuntimeError):
    """模型调用失败的基础异常。"""


class LLMClient(ABC):
    """所有模型客户端必须实现的统一接口（支持非流式与流式）。"""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回当前使用的模型名称。"""

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """是否内置模拟客户端。"""

    @abstractmethod
    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """非流式补全，返回完整文本。失败抛出 LLMClientError。"""

    @abstractmethod
    def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterable[str]:
        """流式补全，逐段返回文本分片。失败抛出 LLMClientError。"""


# 允许在测试中传入自定义响应回调
class ResponseFactory(Protocol):
    """给定历史文本，返回模型回复。用作 MockLLM 的可注入策略。"""

    def __call__(self, history: list[str]) -> str:
        ...