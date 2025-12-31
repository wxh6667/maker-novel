"""模型配置加载器 - 从 YAML 读取 Provider 配置并实例化 LLM。

不依赖 CrewAI，提供独立的配置管理。
"""

from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import yaml

from .adapters.base import BaseLLM

logger = logging.getLogger(__name__)


def _resolve_secret(raw: str | None) -> str | None:
    """Support 直接写值或引用环境变量。"""
    if not raw:
        return None
    token = raw.strip()
    if token.startswith("${") and token.endswith("}"):
        token = token[2:-1]
    if token.isupper():
        val = os.environ.get(token)
        if val is not None:
            return val
        return token
    return token


def resolve_hook(path: str | None) -> Callable | None:
    """Dynamically import a hook function from module path."""
    if not path:
        return None
    target = path.strip()
    if not target:
        return None
    if ":" in target:
        module_name, attr = target.rsplit(":", 1)
    else:
        module_name, attr = target.rsplit(".", 1)
    module = importlib.import_module(module_name)
    hook = getattr(module, attr)
    if not callable(hook):
        raise TypeError(f"Hook {path} is not callable")
    return hook


@dataclass
class ProviderConfig:
    """单个 LLM Provider 的配置。"""

    name: str
    model: str
    provider: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    api_key: str | None = None
    timeout: float = 300.0
    support_json_mode: bool = True
    support_stream: bool = True
    proxy: str | None = None  # 代理地址，支持 socks5://host:port
    embed_api_type: str = "openai"  # embedding API 类型: openai / gemini
    extra: dict[str, Any] = field(default_factory=dict)
    pre_hook: str | None = None
    post_hook: str | None = None

    @classmethod
    def from_mapping(cls, name: str, payload: Mapping[str, Any]) -> ProviderConfig:
        known = {
            key: payload.get(key)
            for key in ("model", "provider", "base_url", "temperature", "max_tokens", "timeout")
        }
        support_json_mode = payload.get("support_json_mode", True)
        support_stream = payload.get("support_stream", True)
        proxy = payload.get("proxy")
        embed_api_type = payload.get("embed_api_type", "openai")
        key = payload.get("api_key")
        pre_hook = payload.get("pre_hook")
        post_hook = payload.get("post_hook")
        extra = {
            k: v
            for k, v in payload.items()
            if k not in {*known.keys(), "api_key", "pre_hook", "post_hook", "support_json_mode", "support_stream", "proxy", "embed_api_type"}
            and v is not None
        }
        resolved_key = _resolve_secret(key) if isinstance(key, str) else key
        return cls(
            name=name,
            api_key=resolved_key,
            extra=extra,
            pre_hook=pre_hook,
            post_hook=post_hook,
            support_json_mode=support_json_mode,
            support_stream=support_stream,
            proxy=proxy,
            embed_api_type=embed_api_type,
            **{k: v for k, v in known.items() if v is not None},  # type: ignore[arg-type]
        )

    def spawn_llm(self) -> BaseLLM:
        """实例化 LLM 对象。"""
        logger.debug(f"[spawn_llm] Provider: {self.provider}, Model: {self.model}, Base URL: {self.base_url}")

        from .adapters.openai_compat import OpenAICompatLLM
        return OpenAICompatLLM(
            model=self.model,
            base_url=self.base_url or "",
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
            support_json_mode=self.support_json_mode,
            support_stream=self.support_stream,
            proxy=self.proxy,
            embed_api_type=self.embed_api_type,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于 API 响应）。"""
        return {
            "name": self.name,
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "has_api_key": bool(self.api_key),
            "support_json_mode": self.support_json_mode,
            "support_stream": self.support_stream,
            "proxy": self.proxy,
            "embed_api_type": self.embed_api_type,
            "pre_hook": self.pre_hook,
            "post_hook": self.post_hook,
        }


class ModelFactory:
    """负责解析 YAML 并实例化 LLM。

    支持单例模式：通过 get_instance() 获取全局共享实例。
    """

    _instance: "ModelFactory | None" = None
    _instance_path: Path | None = None

    def __init__(self, providers: dict[str, ProviderConfig], nodes: dict[str, str] | None = None) -> None:
        self._providers = providers
        self._nodes = nodes or {}

    @classmethod
    def get_instance(cls, path: Path | str | None = None) -> "ModelFactory":
        """获取或创建全局单例实例。"""
        if path is None:
            path = Path(__file__).parent.parent.parent / "config" / "models.yaml"
        path = Path(path)
        if cls._instance is None or cls._instance_path != path:
            cls._instance = cls.from_file(path)
            cls._instance_path = path
        return cls._instance

    @classmethod
    def reload_instance(cls, path: Path | str | None = None) -> "ModelFactory":
        """强制重新加载单例实例。"""
        if path is None:
            path = cls._instance_path
        cls._instance = None
        return cls.get_instance(path)

    @classmethod
    def from_file(cls, path: Path | str) -> "ModelFactory":
        """从 YAML 文件加载配置。"""
        path = Path(path)
        if not path.exists():
            logger.warning(f"未找到模型配置 {path}，使用空配置。")
            return cls(providers={}, nodes={})
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        provider_payload = payload.get("providers", {})
        providers = {
            name: ProviderConfig.from_mapping(name, values or {})
            for name, values in provider_payload.items()
        }
        nodes = payload.get("nodes", {})
        logger.info(f"已加载 {len(providers)} 个 LLM Provider 配置，{len(nodes)} 个节点绑定")
        return cls(providers=providers, nodes=nodes)

    def available_providers(self) -> list[str]:
        """列出所有可用的 Provider 名称。"""
        return sorted(self._providers.keys())

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """获取指定 Provider 的配置（不抛异常）。"""
        return self._providers.get(name)

    def provider_config(self, name: str) -> ProviderConfig:
        """获取指定 Provider 的配置。"""
        provider = self._providers.get(name)
        if not provider:
            raise KeyError(f"未找到模型配置 {name}")
        return provider

    def get_llm(self, provider_name: str) -> BaseLLM:
        """根据 Provider 名称获取 LLM 实例。"""
        provider = self._providers.get(provider_name)
        if not provider:
            raise KeyError(f"未找到模型配置 {provider_name}")
        return provider.spawn_llm()

    def add_provider(self, config: ProviderConfig) -> None:
        """添加新的 Provider 配置。"""
        self._providers[config.name] = config
        logger.info(f"已添加 Provider: {config.name}")

    def remove_provider(self, name: str) -> bool:
        """移除 Provider 配置。"""
        if name in self._providers:
            del self._providers[name]
            logger.info(f"已移除 Provider: {name}")
            return True
        return False

    # ==================== 节点绑定 ====================

    def get_node_bindings(self) -> dict[str, str]:
        """获取所有节点绑定。"""
        return dict(self._nodes)

    def get_node_binding(self, node: str) -> str | None:
        """获取指定节点的绑定。"""
        return self._nodes.get(node)

    def set_node_binding(self, node: str, provider_name: str) -> None:
        """设置节点绑定。"""
        if provider_name and provider_name not in self._providers:
            raise KeyError(f"未找到 Provider: {provider_name}")
        self._nodes[node] = provider_name
        logger.info(f"已设置节点 {node} 绑定为 {provider_name}")

    def llm_for_node(self, node: str) -> BaseLLM:
        """根据节点获取 LLM 实例。"""
        provider_name = self._nodes.get(node)
        if not provider_name:
            # 回退到 default
            provider_name = "default"
            if provider_name not in self._providers:
                raise KeyError(f"节点 {node} 未绑定且无默认 Provider")
        return self.get_llm(provider_name)

    def get_node_model_info(self, node: str) -> dict[str, str]:
        """获取节点绑定的模型信息。"""
        provider_name = self._nodes.get(node, "default")
        provider = self._providers.get(provider_name)
        if not provider:
            return {"node": node, "provider": "", "model": ""}
        return {
            "node": node,
            "provider": provider_name,
            "model": provider.model,
        }

    def save_to_file(self, path: Path | str | None = None) -> None:
        """保存配置到 YAML 文件。"""
        if path is None:
            path = self._instance_path
        if path is None:
            path = Path(__file__).parent.parent.parent / "config" / "models.yaml"
        path = Path(path)

        payload = {
            "providers": {
                name: {
                    "model": cfg.model,
                    "provider": cfg.provider,
                    "base_url": cfg.base_url,
                    "api_key": cfg.api_key,
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                    "timeout": cfg.timeout,
                    "support_json_mode": cfg.support_json_mode,
                    "support_stream": cfg.support_stream,
                    "proxy": cfg.proxy,
                    "embed_api_type": cfg.embed_api_type,
                    "pre_hook": cfg.pre_hook,
                    "post_hook": cfg.post_hook,
                    **cfg.extra,
                }
                for name, cfg in self._providers.items()
            },
            "nodes": self._nodes,
        }

        for provider_data in payload["providers"].values():
            # 移除 None 值
            keys_to_remove = [k for k, v in provider_data.items() if v is None]
            # 移除默认值（减少 YAML 冗余）
            if provider_data.get("support_json_mode") is True:
                keys_to_remove.append("support_json_mode")
            if provider_data.get("support_stream") is True:
                keys_to_remove.append("support_stream")
            if provider_data.get("embed_api_type") == "openai":
                keys_to_remove.append("embed_api_type")
            for k in keys_to_remove:
                provider_data.pop(k, None)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.dump(payload, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        logger.debug(f"配置已保存到 {path}")


__all__ = ["ModelFactory", "ProviderConfig", "resolve_hook"]
