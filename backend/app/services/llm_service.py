import asyncio
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import HTTPException
from pydantic import BaseModel

from ..repositories.system_config_repository import SystemConfigRepository
from ..services.usage_service import UsageService
from ..services.provider_service import get_provider_service, ProviderService
from ..llm.adapters.base import BaseLLM
from ..utils.retry_utils import is_retryable_error, calculate_retry_delay, DEFAULT_MAX_ATTEMPTS, DEFAULT_BACKOFFS

logger = logging.getLogger(__name__)


class LLMService:
    """LLM 调用服务。

    负责 LLM 调用和 Embedding 生成。
    Provider 管理委托给 ProviderService。
    """

    def __init__(self, session):
        self.session = session
        self.system_config_repo = SystemConfigRepository(session)
        self.usage_service = UsageService(session)
        self._embedding_dimensions: Dict[str, int] = {}
        self._provider_service: ProviderService = get_provider_service()

    # ==================== Provider 代理方法 ====================

    def get_available_providers(self) -> List[str]:
        """获取所有可用的 Provider 名称。"""
        return self._provider_service.get_available_providers()

    def get_provider_config(self, name: str):
        """获取指定 Provider 的配置。"""
        return self._provider_service.get_provider_config(name)

    def get_all_provider_configs(self) -> List[Dict[str, Any]]:
        """获取所有 Provider 的详细配置。"""
        return self._provider_service.get_all_provider_configs()

    def add_provider(self, **kwargs) -> Dict[str, Any]:
        """添加新的 Provider 配置。"""
        return self._provider_service.add_provider(**kwargs)

    def update_provider(self, name: str, **kwargs) -> Dict[str, Any]:
        """更新已有的 Provider 配置。"""
        return self._provider_service.update_provider(name, **kwargs)

    def remove_provider(self, name: str) -> bool:
        """删除 Provider 配置。"""
        return self._provider_service.remove_provider(name)

    def get_node_bindings(self) -> Dict[str, str]:
        """获取所有节点绑定。"""
        return self._provider_service.get_node_bindings()

    def get_node_model_info(self, node: str) -> Dict[str, str]:
        """获取节点绑定的模型信息。"""
        return self._provider_service.get_node_model_info(node)

    def set_node_binding(self, node: str, provider_name: str) -> None:
        """设置节点绑定。"""
        self._provider_service.set_node_binding(node, provider_name)

    async def test_provider_connection(self, provider_name: str, test_prompt: Optional[str] = None) -> Dict[str, Any]:
        """测试指定 Provider 连接。"""
        return await self._provider_service.test_provider_connection(provider_name, test_prompt)

    async def test_provider_json_mode(self, provider_name: str) -> Dict[str, Any]:
        """测试 Provider JSON 模式。"""
        return await self._provider_service.test_provider_json_mode(provider_name)

    # ==================== LLM 调用 ====================

    def _get_llm_for_node(self, node: str) -> BaseLLM:
        """根据节点获取 LLM 实例。"""
        return self._provider_service.get_llm_for_node(node)

    def _get_llm_for_provider(self, provider_name: str) -> BaseLLM:
        """根据 Provider 名称获取 LLM 实例。"""
        return self._provider_service.get_llm_for_provider(provider_name)

    async def call_node(
        self,
        node: str,
        messages: List[Dict[str, str]] | str,
        *,
        user_id: Optional[int] = None,
        response_model: Optional[type[BaseModel]] = None,
        response_format: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """使用指定节点的 LLM 进行调用。"""
        llm = self._get_llm_for_node(node)

        try:
            for attempt in range(DEFAULT_MAX_ATTEMPTS):
                try:
                    result = await llm.acall(
                        messages,
                        response_model=response_model,
                        response_format=response_format,
                        **kwargs,
                    )
                    await self.usage_service.increment("api_request_count")
                    return result
                except Exception as exc:
                    if is_retryable_error(exc) and attempt < DEFAULT_MAX_ATTEMPTS - 1:
                        delay = calculate_retry_delay(exc, attempt, DEFAULT_BACKOFFS)
                        logger.warning(
                            "LLM call failed for node %s (attempt %s/%s), retrying in %ss: %s",
                            node,
                            attempt + 1,
                            DEFAULT_MAX_ATTEMPTS,
                            delay,
                            exc,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise
        except Exception as exc:
            logger.error("LLM call failed for node %s: %s", node, exc, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=f"AI 服务调用失败: {str(exc)}"
            ) from exc

    async def stream_node(
        self,
        node: str,
        messages: List[Dict[str, str]] | str,
        *,
        user_id: Optional[int] = None,
        response_format: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """使用指定节点的 LLM 进行流式调用。"""
        llm = self._get_llm_for_node(node)
        last_exc: Exception | None = None

        for attempt in range(DEFAULT_MAX_ATTEMPTS):
            try:
                async for chunk in llm.astream(
                    messages,
                    response_format=response_format,
                    **kwargs,
                ):
                    yield chunk
                await self.usage_service.increment("api_request_count")
                return
            except Exception as exc:
                last_exc = exc
                if is_retryable_error(exc) and attempt < DEFAULT_MAX_ATTEMPTS - 1:
                    delay = calculate_retry_delay(exc, attempt, DEFAULT_BACKOFFS)
                    logger.warning(
                        "LLM stream failed for node %s (attempt %s/%s), retrying in %ss: %s",
                        node,
                        attempt + 1,
                        DEFAULT_MAX_ATTEMPTS,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        if last_exc:
            logger.error("LLM stream failed for node %s: %s", node, last_exc, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=f"AI 服务流式调用失败: {str(last_exc)}"
            ) from last_exc

    async def stream_with_provider(
        self,
        provider_name: str,
        messages: List[Dict[str, str]] | str,
        *,
        response_format: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """使用指定 Provider 进行流式调用。"""
        llm = self._get_llm_for_provider(provider_name)
        last_exc: Exception | None = None

        for attempt in range(DEFAULT_MAX_ATTEMPTS):
            try:
                async for chunk in llm.astream(
                    messages,
                    response_format=response_format,
                    **kwargs,
                ):
                    yield chunk
                await self.usage_service.increment("api_request_count")
                return
            except Exception as exc:
                last_exc = exc
                if is_retryable_error(exc) and attempt < DEFAULT_MAX_ATTEMPTS - 1:
                    delay = calculate_retry_delay(exc, attempt, DEFAULT_BACKOFFS)
                    logger.warning(
                        "LLM stream failed for provider %s (attempt %s/%s), retrying in %ss: %s",
                        provider_name,
                        attempt + 1,
                        DEFAULT_MAX_ATTEMPTS,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        if last_exc:
            logger.error("LLM stream failed for provider %s: %s", provider_name, last_exc, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=f"AI 服务流式调用失败: {str(last_exc)}"
            ) from last_exc

    async def call_with_provider(
        self,
        provider_name: str,
        messages: List[Dict[str, str]],
        *,
        response_model: Optional[type[BaseModel]] = None,
        response_format: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """使用指定 Provider 进行调用。"""
        llm = self._get_llm_for_provider(provider_name)

        try:
            for attempt in range(DEFAULT_MAX_ATTEMPTS):
                try:
                    result = await llm.acall(
                        messages,
                        response_model=response_model,
                        response_format=response_format,
                        **kwargs,
                    )
                    await self.usage_service.increment("api_request_count")
                    return result
                except Exception as exc:
                    if is_retryable_error(exc) and attempt < DEFAULT_MAX_ATTEMPTS - 1:
                        delay = calculate_retry_delay(exc, attempt, DEFAULT_BACKOFFS)
                        logger.warning(
                            "LLM call failed for provider %s (attempt %s/%s), retrying in %ss: %s",
                            provider_name,
                            attempt + 1,
                            DEFAULT_MAX_ATTEMPTS,
                            delay,
                            exc,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise
        except Exception as exc:
            logger.error("LLM call failed for provider %s: %s", provider_name, exc, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=f"AI 服务调用失败: {str(exc)}"
            ) from exc

    # ==================== Embedding ====================

    async def get_embedding(
        self,
        text: str,
        *,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """生成文本向量，用于章节 RAG 检索。

        使用 models.yaml 中配置的 embedding 节点。
        """
        llm = self._get_llm_for_node("embedding")
        logger.debug("使用节点路由获取 embedding: provider=%s", llm.provider)
        embedding = await llm.aembed(text, model=model)
        if embedding:
            dimension = len(embedding)
            if dimension:
                target_model = model or llm.model
                self._embedding_dimensions[target_model] = dimension
        return embedding

    async def get_embedding_dimension(self, model: Optional[str] = None) -> Optional[int]:
        """获取嵌入向量维度。"""
        default_model = await self._get_config_value("embedding.model") or "text-embedding-3-large"
        target_model = model or default_model
        if target_model in self._embedding_dimensions:
            return self._embedding_dimensions[target_model]
        vector_size_str = await self._get_config_value("embedding.model_vector_size")
        return int(vector_size_str) if vector_size_str else None

    async def _get_config_value(self, key: str) -> Optional[str]:
        """从系统配置或环境变量获取配置值。"""
        record = await self.system_config_repo.get_by_key(key)
        if record:
            return record.value
        env_key = key.upper().replace(".", "_")
        return os.getenv(env_key)
