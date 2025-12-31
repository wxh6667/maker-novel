"""OpenAI 兼容 API 适配器（异步版本）。

用于连接标准 OpenAI 兼容的第三方 API（如代理服务）。
支持标准的 /v1/chat/completions 端点和流式响应格式。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx
from pydantic import BaseModel, ValidationError

from .base import BaseLLM
from ..structured_guard import (
    append_system_message,
    build_schema_hint,
    summarize_validation_error,
    validate_against_model,
)

logger = logging.getLogger(__name__)


class OpenAICompatLLM(BaseLLM):
    """OpenAI 兼容 API 适配器（异步版本）。

    用于连接标准 OpenAI 格式的第三方 API，支持：
    - POST /v1/chat/completions
    - 标准 messages 格式
    - 流式响应 (SSE)
    - 异步调用
    """

    MAX_STRUCTURED_ATTEMPTS = 3

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: float = 300.0,
        support_json_mode: bool = True,
        support_stream: bool = True,
        proxy: Optional[str] = None,
        embed_api_type: str = "openai",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            base_url=base_url,
            api_key=api_key,
            provider="openai_compat",
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        self._timeout = timeout
        self._support_json_mode = support_json_mode
        self._support_stream = support_stream
        self._proxy = proxy
        self._embed_api_type = embed_api_type

    def _format_messages(
        self, messages: Union[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """格式化消息为标准格式。"""
        if isinstance(messages, str):
            return [{"role": "user", "content": messages}]
        return [
            {"role": msg.get("role", "user"), "content": msg.get("content", "")}
            for msg in messages
        ]

    def _build_url(self) -> str:
        """构建完整的 API URL。"""
        url = self.base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            if url.endswith("/v1"):
                url = f"{url}/chat/completions"
            else:
                url = f"{url}/v1/chat/completions"
        return url

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头。"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ArborisNovel/1.0",
        }

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = True,
        temperature_override: Optional[float] = None,
        response_format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """构建请求体。"""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if temperature_override is not None:
            payload["temperature"] = temperature_override
        elif self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        # 只有当 support_json_mode 为 True 时才添加 response_format
        if response_format and self._support_json_mode:
            payload["response_format"] = {"type": response_format}
        return payload

    async def acall(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        *,
        response_model: Optional[type[BaseModel]] = None,
        response_format: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """异步调用 LLM。"""
        temperature_override = kwargs.pop("temperature_override", None)
        timeout_override = kwargs.pop("timeout", None)
        formatted_messages = self._format_messages(messages)
        url = self._build_url()
        headers = self._build_headers()

        schema_hint = None
        attempts = 1
        if response_model:
            schema_hint = build_schema_hint(response_model)
            attempts = self.MAX_STRUCTURED_ATTEMPTS

        last_error: str | None = None

        for attempt in range(attempts):
            attempt_messages = formatted_messages
            if schema_hint:
                hint = (
                    schema_hint
                    if attempt == 0
                    else f"⚠️ 结构化输出未通过校验：{last_error}\n{schema_hint}"
                )
                attempt_messages = append_system_message(formatted_messages, hint)

            payload = self._build_payload(
                attempt_messages,
                stream=False,
                temperature_override=temperature_override,
                response_format=response_format,
            )

            try:
                actual_timeout = timeout_override if timeout_override is not None else self._timeout
                async with httpx.AsyncClient(timeout=actual_timeout, verify=False) as client:
                    response = await client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    error_detail = response.text[:500]
                    raise ValueError(f"API Error {response.status_code}: {error_detail}")

                data = response.json()
                completion_text = data["choices"][0]["message"]["content"]

                if not response_model:
                    return completion_text

                try:
                    normalized, _ = validate_against_model(response_model, completion_text)
                    return normalized
                except ValidationError as exc:
                    last_error = summarize_validation_error(exc)
                    logger.warning(
                        "[OpenAICompat] Structured output validation failed (attempt %s/%s): %s",
                        attempt + 1,
                        attempts,
                        last_error,
                    )
                    continue

            except httpx.TimeoutException as exc:
                raise RuntimeError(f"Request timeout: {exc}") from exc
            except httpx.ConnectError as exc:
                raise RuntimeError(f"Connection failed: {exc}") from exc
            except Exception as exc:
                raise RuntimeError(f"OpenAI-compat async call failed: {exc}") from exc

        raise RuntimeError(
            f"OpenAI-compat structured output failed after {attempts} attempts: {last_error}"
        )

    async def astream(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        response_format: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """异步流式调用 LLM。不支持流式时自动降级为非流式调用。"""
        # 不支持流式时，自动降级为非流式调用
        if not self._support_stream:
            result = await self.acall(messages, response_format=response_format, **kwargs)
            yield {"content": result, "finish_reason": "stop"}
            return

        temperature_override = kwargs.pop("temperature_override", None)
        formatted_messages = self._format_messages(messages)
        url = self._build_url()
        headers = self._build_headers()
        payload = self._build_payload(
            formatted_messages,
            stream=True,
            temperature_override=temperature_override,
            response_format=response_format,
        )

        logger.debug(f"[OpenAICompat] POST {url} (streaming), response_format={payload.get('response_format')}, support_json_mode={self._support_json_mode}")

        async with httpx.AsyncClient(timeout=self._timeout, verify=False) as client:
            async with client.stream(
                "POST", url, headers=headers, json=payload
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise ValueError(
                        f"API Error {response.status_code}: {error_text.decode()[:500]}"
                    )

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                choice = choices[0]
                                delta = choice.get("delta", {})
                                content = delta.get("content")
                                finish_reason = choice.get("finish_reason")

                                yield {
                                    "content": content,
                                    "finish_reason": finish_reason,
                                }
                        except json.JSONDecodeError as json_err:
                            logger.debug(
                                "[OpenAICompat] JSON decode error: %s, line: %s",
                                json_err,
                                data_str[:200],
                            )
                            continue


    def _get_http_client(self, **kwargs: Any) -> httpx.AsyncClient:
        """创建 HTTP 客户端，支持 SOCKS 代理。"""
        client_kwargs: Dict[str, Any] = {
            "timeout": self._timeout,
            "verify": False,
            **kwargs,
        }
        if self._proxy:
            client_kwargs["proxy"] = self._proxy
        return httpx.AsyncClient(**client_kwargs)

    async def aembed(
        self,
        text: str,
        *,
        model: Optional[str] = None,
    ) -> List[float]:
        """生成文本向量嵌入，支持 OpenAI 和 Gemini API。

        Args:
            text: 要嵌入的文本
            model: 可选的模型名称，覆盖默认模型

        Returns:
            向量列表
        """
        target_model = model or self.model

        if self._embed_api_type == "gemini":
            return await self._aembed_gemini(text, target_model)
        return await self._aembed_openai(text, target_model)

    async def _aembed_openai(self, text: str, target_model: str) -> List[float]:
        """OpenAI 兼容格式的 Embedding。"""
        url = self.base_url.rstrip("/")
        if url.endswith("/chat/completions"):
            url = url.rsplit("/chat/completions", 1)[0]
        if not url.endswith("/v1"):
            url = f"{url}/v1"
        url = f"{url}/embeddings"

        headers = self._build_headers()
        payload = {
            "model": target_model,
            "input": text,
        }

        logger.debug(f"[OpenAICompat] Embedding request: model={target_model}, proxy={self._proxy}")

        try:
            async with self._get_http_client() as client:
                response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                error_detail = response.text[:500]
                logger.error(f"[OpenAICompat] Embedding failed: {response.status_code} - {error_detail}")
                return []

            data = response.json()
            if not data.get("data"):
                logger.warning("[OpenAICompat] Embedding response has no data")
                return []

            embedding = data["data"][0].get("embedding", [])
            if not isinstance(embedding, list):
                embedding = list(embedding)
            return embedding

        except Exception as exc:
            logger.error(f"[OpenAICompat] Embedding request failed: {exc}", exc_info=True)
            return []

    async def _aembed_gemini(self, text: str, target_model: str) -> List[float]:
        """Google Gemini Embedding API 格式。

        API: POST https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={api_key}
        """
        # 构建 Gemini API URL
        base = self.base_url.rstrip("/")
        if not base:
            base = "https://generativelanguage.googleapis.com"
        # 移除可能存在的 /v1 后缀
        if base.endswith("/v1") or base.endswith("/v1beta"):
            base = base.rsplit("/", 1)[0]

        url = f"{base}/v1beta/models/{target_model}:embedContent?key={self.api_key}"

        headers = {"Content-Type": "application/json"}
        payload = {
            "model": f"models/{target_model}",
            "content": {
                "parts": [{"text": text}]
            }
        }

        logger.debug(f"[Gemini] Embedding request: model={target_model}, proxy={self._proxy}")

        try:
            async with self._get_http_client() as client:
                response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                error_detail = response.text[:500]
                logger.error(f"[Gemini] Embedding failed: {response.status_code} - {error_detail}")
                return []

            data = response.json()
            embedding_data = data.get("embedding", {})
            embedding = embedding_data.get("values", [])
            if not isinstance(embedding, list):
                embedding = list(embedding)
            return embedding

        except Exception as exc:
            logger.error(f"[Gemini] Embedding request failed: {exc}", exc_info=True)
            return []

    def supports_function_calling(self) -> bool:
        """检查是否支持函数调用。"""
        return True


__all__ = ["OpenAICompatLLM"]
