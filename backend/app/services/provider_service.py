import logging
from time import perf_counter
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from ..llm.config import ModelFactory, ProviderConfig
from ..llm.adapters.base import BaseLLM

logger = logging.getLogger(__name__)


class ProviderService:
    """Provider 管理服务。

    负责 Provider 的 CRUD 操作、节点绑定和连接测试。
    """

    def __init__(self):
        self._model_factory: Optional[ModelFactory] = None

    @property
    def model_factory(self) -> ModelFactory:
        """获取 ModelFactory 实例（懒加载）。"""
        if self._model_factory is None:
            self._model_factory = ModelFactory.get_instance()
        return self._model_factory

    # ==================== Provider CRUD ====================

    def get_llm_for_provider(self, provider_name: str) -> BaseLLM:
        """根据 Provider 名称获取 LLM 实例。"""
        return self.model_factory.get_llm(provider_name)

    def get_available_providers(self) -> List[str]:
        """获取所有可用的 Provider 名称。"""
        return self.model_factory.available_providers()

    def get_provider_config(self, name: str) -> Optional[ProviderConfig]:
        """获取指定 Provider 的配置。"""
        return self.model_factory.get_provider(name)

    def get_all_provider_configs(self) -> List[Dict[str, Any]]:
        """获取所有 Provider 的详细配置（不含敏感信息）。"""
        result = []
        for name in self.model_factory.available_providers():
            config = self.model_factory.get_provider(name)
            if config:
                result.append(config.to_dict())
        return result

    def add_provider(
        self,
        name: str,
        model: str,
        provider: Optional[str] = "openai_compat",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = 0.5,
        max_tokens: Optional[int] = 4096,
        timeout: Optional[float] = 300.0,
        support_json_mode: bool = True,
        support_stream: bool = True,
        proxy: Optional[str] = None,
        embed_api_type: str = "openai",
    ) -> Dict[str, Any]:
        """添加新的 Provider 配置。"""
        config = ProviderConfig(
            name=name,
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            support_json_mode=support_json_mode,
            support_stream=support_stream,
            proxy=proxy,
            embed_api_type=embed_api_type,
        )
        self.model_factory.add_provider(config)
        self.model_factory.save_to_file()
        return config.to_dict()

    def update_provider(
        self,
        name: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        support_json_mode: Optional[bool] = None,
        support_stream: Optional[bool] = None,
        proxy: Optional[str] = None,
        embed_api_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """更新已有的 Provider 配置。

        注意：空字符串 "" 表示清空字段，None 表示保留原值。
        """
        existing = self.model_factory.get_provider(name)
        if not existing:
            raise KeyError(f"Provider {name} 不存在")

        def resolve(new_val, old_val):
            """空字符串清空，None 保留原值，其他值更新。"""
            if new_val is None:
                return old_val
            if new_val == "":
                return None
            return new_val

        updated = ProviderConfig(
            name=name,
            model=model if model is not None else existing.model,
            provider=provider if provider is not None else existing.provider,
            base_url=resolve(base_url, existing.base_url),
            api_key=resolve(api_key, existing.api_key),
            temperature=temperature if temperature is not None else existing.temperature,
            max_tokens=max_tokens if max_tokens is not None else existing.max_tokens,
            timeout=timeout if timeout is not None else existing.timeout,
            support_json_mode=support_json_mode if support_json_mode is not None else existing.support_json_mode,
            support_stream=support_stream if support_stream is not None else existing.support_stream,
            proxy=resolve(proxy, existing.proxy),
            embed_api_type=embed_api_type if embed_api_type is not None else existing.embed_api_type,
        )
        self.model_factory.add_provider(updated)
        self.model_factory.save_to_file()
        return updated.to_dict()

    def remove_provider(self, name: str) -> bool:
        """删除 Provider 配置。"""
        result = self.model_factory.remove_provider(name)
        if result:
            self.model_factory.save_to_file()
        return result

    # ==================== 节点绑定 ====================

    def get_node_bindings(self) -> Dict[str, str]:
        """获取所有节点绑定。"""
        return self.model_factory.get_node_bindings()

    def get_llm_for_node(self, node: str) -> BaseLLM:
        """根据节点获取 LLM 实例。"""
        return self.model_factory.llm_for_node(node)

    def get_node_model_info(self, node: str) -> Dict[str, str]:
        """获取节点绑定的模型信息。"""
        return self.model_factory.get_node_model_info(node)

    def set_node_binding(self, node: str, provider_name: str) -> None:
        """设置节点绑定。"""
        self.model_factory.set_node_binding(node, provider_name)
        self.model_factory.save_to_file()

    # ==================== 连接测试 ====================

    async def test_provider_connection(
        self,
        provider_name: str,
        test_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """测试指定 Provider 连接是否可用。"""
        config = self.get_provider_config(provider_name)
        if not config:
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")

        if not config.api_key:
            raise HTTPException(status_code=400, detail="该 Provider 未配置 API Key")

        # 检测是否是 embedding 模型
        is_embedding_model = "embedding" in config.model.lower()

        # 仅 embedding 且 Gemini 才允许 base_url 为空（使用默认地址）
        is_gemini_embed = is_embedding_model and config.embed_api_type == "gemini"
        if not config.base_url and not is_gemini_embed:
            raise HTTPException(status_code=400, detail="该 Provider 未配置 Base URL")

        llm = self.get_llm_for_provider(provider_name)
        message = test_prompt or "ping"

        start = perf_counter()
        try:
            if is_embedding_model:
                # embedding 模型使用 aembed 测试
                embedding = await llm.aembed(message)
                latency_ms = int((perf_counter() - start) * 1000)
                if embedding:
                    preview = f"向量维度: {len(embedding)}"
                else:
                    raise ValueError("Embedding 返回空结果")
            else:
                # LLM 模型使用 acall 测试
                response = await llm.acall(message, response_format=None)
                latency_ms = int((perf_counter() - start) * 1000)
                preview = response.strip()
                if len(preview) > 200:
                    preview = preview[:200]
            return {
                "ok": True,
                "latency_ms": latency_ms,
                "model": config.model,
                "base_url": config.base_url,
                "response_preview": preview,
                "error": None,
            }
        except Exception as exc:
            latency_ms = int((perf_counter() - start) * 1000)
            logger.warning("Provider %s 连接测试失败: %s", provider_name, exc)
            return {
                "ok": False,
                "latency_ms": latency_ms,
                "model": config.model,
                "base_url": config.base_url,
                "response_preview": None,
                "error": str(exc),
            }

    async def test_provider_json_mode(
        self,
        provider_name: str,
    ) -> Dict[str, Any]:
        """测试 Provider 是否支持 JSON 模式输出。"""
        config = self.get_provider_config(provider_name)
        if not config:
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")

        if not config.api_key:
            raise HTTPException(status_code=400, detail="该 Provider 未配置 API Key")
        if not config.base_url:
            raise HTTPException(status_code=400, detail="该 Provider 未配置 Base URL")

        # embedding 模型不支持 JSON 模式
        if "embedding" in config.model.lower():
            return {
                "ok": False,
                "latency_ms": 0,
                "model": config.model,
                "base_url": config.base_url,
                "response_preview": None,
                "json_valid": False,
                "error": "Embedding 模型不支持 JSON 模式",
            }

        llm = self.get_llm_for_provider(provider_name)
        test_prompt = '请返回一个JSON对象，包含字段 "status": "ok", "message": "测试成功"'

        start = perf_counter()
        try:
            response = await llm.acall(test_prompt, response_format="json_object")
            latency_ms = int((perf_counter() - start) * 1000)

            # 使用统一的 JSON 清理函数
            import json
            from app.utils.json_utils import unwrap_markdown_json, sanitize_json_like_text
            cleaned = sanitize_json_like_text(unwrap_markdown_json(response.strip()))

            # 验证返回是否为有效 JSON
            try:
                parsed = json.loads(cleaned)
                json_valid = True
                preview = json.dumps(parsed, ensure_ascii=False)[:200]
            except json.JSONDecodeError:
                json_valid = False
                preview = response.strip()[:200]

            return {
                "ok": True,
                "latency_ms": latency_ms,
                "model": config.model,
                "base_url": config.base_url,
                "response_preview": preview,
                "json_valid": json_valid,
                "error": None if json_valid else "返回内容不是有效 JSON",
            }
        except Exception as exc:
            latency_ms = int((perf_counter() - start) * 1000)
            logger.warning("Provider %s JSON 模式测试失败: %s", provider_name, exc)
            return {
                "ok": False,
                "latency_ms": latency_ms,
                "model": config.model,
                "base_url": config.base_url,
                "response_preview": None,
                "json_valid": False,
                "error": str(exc),
            }


# 单例实例
_provider_service: Optional[ProviderService] = None


def get_provider_service() -> ProviderService:
    """获取 ProviderService 单例实例。"""
    global _provider_service
    if _provider_service is None:
        _provider_service = ProviderService()
    return _provider_service
