"""内置模拟 LLM 客户端。

用途：
- 无 API Key 时保证系统可离线端到端运行；
- 测试时注入确定性回复，便于断言。

默认行为：若未注入 ``response_factory``，则根据 user 消息内容返回简洁的占位回复，
并把最后一个系统提示中的 JSON 要求尽量仿真为可解析的 JSON。
"""

from __future__ import annotations

import json
import re
from typing import Iterable

from .base import ChatMessage, LLMClient, ResponseFactory


class MockLLMClient(LLMClient):
    """确定性、可离线、可注入策略的模拟客户端。"""

    def __init__(
        self,
        *,
        model_name: str = "mock-model",
        response_factory: ResponseFactory | None = None,
        echo_last_user: bool = False,
    ) -> None:
        self._model_name = model_name
        self._response_factory = response_factory
        self._echo_last_user = echo_last_user

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_mock(self) -> bool:
        return True

    def _history(self, messages: list[ChatMessage]) -> list[str]:
        return [f"{m.role}: {m.content}" for m in messages]

    def _render(self, messages: list[ChatMessage]) -> str:
        if self._response_factory is not None:
            return self._response_factory(self._history(messages))
        if not messages:
            return ""
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        # 仿真：如果提示要求返回 JSON，则给一个最小可解析 JSON
        joined = " ".join(m.content for m in messages)
        if "json" in joined.lower() or "JSON" in joined:
            return json.dumps({"ok": True, "note": "mock default json reply"})
        if self._echo_last_user:
            return last_user
        # 默认回复一句占位说明
        excerpt = re.sub(r"\s+", " ", last_user)[:120]
        return f"[mock] 已收到需求，可在此注入真实 LLM。需求摘要：{excerpt}"

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return self._render(messages)

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterable[str]:
        text = self._render(messages)
        for i in range(0, len(text), 16):
            yield text[i : i + 16]