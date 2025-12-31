"""LLM 灵活配置层 - 支持多 Provider 和角色绑定。

移植自 maker_stream，适配 arboris-novel 的异步架构。
"""

from .config import ModelFactory, ProviderConfig
from .encoding_fix import ensure_utf8_json, fix_garbled_chinese
from .structured_guard import (
    build_schema_hint,
    normalize_json_payload,
    validate_against_model,
)

__all__ = [
    "ModelFactory",
    "ProviderConfig",
    "ensure_utf8_json",
    "fix_garbled_chinese",
    "build_schema_hint",
    "normalize_json_payload",
    "validate_against_model",
]
