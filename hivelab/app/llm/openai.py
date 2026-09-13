"""OpenAI 兼容的 HTTP 模型客户端。

通过 `httpx` 调用 `POST {base}/chat/completions`，兼容 OpenAI / DeepSeek /
通义 / GLM 等一切遵循该协议的厂商。自带超时、重试与指数退避。
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Iterable

import httpx

from .base import ChatMessage, LLMClient, LLMClientError

logger = logging.getLogger("hivelab.llm.openai")


class OpenAICompatClient(LLMClient):
    """OpenAI 兼容客户端。"""

    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        model: str,
        timeout: float = 120,
        max_retries: int = 3,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        stream_enabled: bool = False,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_retries = max(0, max_retries)
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._stream_enabled = stream_enabled

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def is_mock(self) -> bool:
        return False

    def _endpoint(self) -> str:
        return f"{self._api_base}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool = False,
    ) -> dict[str, Any]:
        return {
            "model": self._model,
            "messages": [m.model_dump() for m in messages],
            "temperature": self._temperature if temperature is None else temperature,
            "max_tokens": self._max_tokens if max_tokens is None else max_tokens,
            "stream": stream,
        }

    def _retry_delay(self, attempt: int) -> float:
        """指数退避 + 抖动。"""
        return min(0.5 * (2 ** attempt), 8.0) + random.uniform(0, 0.2)

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                time.sleep(self._retry_delay(attempt - 1))
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(
                        self._endpoint(),
                        headers=self._headers(),
                        json=self._payload(
                            messages, temperature=temperature, max_tokens=max_tokens
                        ),
                    )
                if resp.status_code != 200:
                    raise LLMClientError(
                        f"LLM HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                return self._extract_content(resp.json())
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)\
                    as exc:  # noqa: E501
                last_err = exc
                logger.warning("LLM 请求失败(第%d次): %s", attempt + 1, exc)
                if isinstance(exc, httpx.TimeoutException) and attempt >= self._max_retries:
                    break
            except LLMClientError:
                raise
            except Exception as exc:  # 解析错误等
                raise LLMClientError(f"LLM 调用异常: {exc}") from exc
        raise LLMClientError(
            f"LLM 请求在 {self._max_retries + 1} 次尝试后仍未成功: {last_err}"
        )

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterable[str]:
        """阻塞读取 SSE 流式响应。"""
        with httpx.Client(timeout=self._timeout) as client:
            with client.stream(
                "POST",
                self._endpoint(),
                headers=self._headers(),
                json=self._payload(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                ),
            ) as resp:
                if resp.status_code != 200:
                    raise LLMClientError(
                        f"LLM HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                for line in resp.iter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = (
                        chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content")
                    )
                    if delta:
                        yield delta

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(
                f"LLM 返回格式不符: {json.dumps(data)[:300]}"
            ) from exc