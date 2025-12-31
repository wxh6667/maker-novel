"""LLM 适配器基类 - 定义统一的 LLM 调用接口。

不依赖 CrewAI，提供独立的抽象基类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from pydantic import BaseModel


class BaseLLM(ABC):
    """LLM 适配器抽象基类。

    定义统一的调用接口，支持：
    - 异步调用 (acall)
    - 异步流式调用 (astream)
    - 结构化输出 (response_model)
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._extra = kwargs

    @abstractmethod
    async def acall(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        *,
        response_model: Optional[type[BaseModel]] = None,
        **kwargs: Any,
    ) -> str:
        """异步调用 LLM。

        Args:
            messages: 消息列表或单个字符串
            response_model: 可选的 Pydantic 模型，用于结构化输出
            **kwargs: 其他参数

        Returns:
            LLM 响应文本
        """
        ...

    @abstractmethod
    async def astream(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """异步流式调用 LLM。

        Args:
            messages: 消息列表或单个字符串
            **kwargs: 其他参数

        Yields:
            包含 content 和 finish_reason 的字典
        """
        ...


    async def aembed(
        self,
        text: str,
        *,
        model: Optional[str] = None,
    ) -> List[float]:
        """生成文本向量嵌入。

        Args:
            text: 要嵌入的文本
            model: 可选的模型名称，覆盖默认模型

        Returns:
            向量列表
        """
        raise NotImplementedError("此适配器不支持 embedding")

    def supports_function_calling(self) -> bool:
        """检查是否支持函数调用。"""
        return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model!r}, provider={self.provider!r})"


__all__ = ["BaseLLM"]
