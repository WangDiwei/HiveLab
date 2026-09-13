"""模型客户端工厂：根据配置选择真实客户端或 MockLLM。"""

from __future__ import annotations

from ..config import ProviderMode, Settings
from .base import LLMClient
from .mock import MockLLMClient, ResponseFactory
from .openai import OpenAICompatClient


def create_client(
    *,
    api_base: str,
    api_key: str,
    model: str,
    provider_mode: ProviderMode = ProviderMode.AUTO,
    mock_provider: bool = True,
    timeout: float = 120,
    max_retries: int = 3,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    stream_enabled: bool = False,
    response_factory: ResponseFactory | None = None,
) -> LLMClient:
    """根据配置构造模型客户端。

    - ``mock`` 模式：始终返回 MockLLMClient。
    - ``real`` 模式：缺少 key 抛错，否则返回真实客户端。
    - ``auto`` 模式：有无 key + api_base 则返回真实客户端，否则 MockLLMClient。
    """
    use_real = bool(api_base and api_key and model)
    if provider_mode == ProviderMode.MOCK or (
        provider_mode == ProviderMode.AUTO and not use_real and mock_provider
    ):
        return MockLLMClient(response_factory=response_factory)
    if not use_real:
        if provider_mode == ProviderMode.REAL:
            raise ValueError("ProviderMode=real 但未配置 API Base/Key/Model")
        # AUTO 但 mock_provider=False 且不可用
        raise ValueError("模型服务商未配置，且已禁用内置模拟模型")
    return OpenAICompatClient(
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout=timeout,
        max_retries=max_retries,
        temperature=temperature,
        max_tokens=max_tokens,
        stream_enabled=stream_enabled,
    )


def build_default_client(
    settings: Settings,
    response_factory: ResponseFactory | None = None,
) -> LLMClient:
    """从全局配置便利地构造默认客户端。"""
    return create_client(
        api_base=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        provider_mode=settings.llm_provider,
        mock_provider=settings.mock_provider,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        stream_enabled=settings.llm_stream,
        response_factory=response_factory,
    )