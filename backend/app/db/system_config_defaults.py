from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..core.config import Settings


def _to_optional_str(value: Optional[object]) -> Optional[str]:
    return str(value) if value is not None else None


def _bool_to_text(value: bool) -> str:
    return "true" if value else "false"


@dataclass(frozen=True)
class SystemConfigDefault:
    key: str
    value_getter: Callable[[Settings], Optional[str]]
    description: Optional[str] = None


SYSTEM_CONFIG_DEFAULTS: list[SystemConfigDefault] = [
    SystemConfigDefault(
        key="llm.api_key",
        value_getter=lambda config: config.openai_api_key,
        description="默认 LLM API Key，用于后台调用大模型。",
    ),
    SystemConfigDefault(
        key="llm.base_url",
        value_getter=lambda config: _to_optional_str(config.openai_base_url),
        description="默认大模型 API Base URL。",
    ),
    SystemConfigDefault(
        key="llm.model",
        value_getter=lambda config: config.openai_model_name,
        description="默认 LLM 模型名称。",
    ),
    SystemConfigDefault(
        key="smtp.server",
        value_getter=lambda config: config.smtp_server,
        description="用于发送邮件验证码的 SMTP 服务器地址。",
    ),
    SystemConfigDefault(
        key="smtp.port",
        value_getter=lambda config: _to_optional_str(config.smtp_port),
        description="SMTP 服务端口。",
    ),
    SystemConfigDefault(
        key="smtp.username",
        value_getter=lambda config: config.smtp_username,
        description="SMTP 登录用户名。",
    ),
    SystemConfigDefault(
        key="smtp.password",
        value_getter=lambda config: config.smtp_password,
        description="SMTP 登录密码。",
    ),
    SystemConfigDefault(
        key="smtp.from",
        value_getter=lambda config: config.email_from,
        description="邮件显示的发件人名称或邮箱。",
    ),
    SystemConfigDefault(
        key="auth.allow_registration",
        value_getter=lambda config: _bool_to_text(config.allow_registration),
        description="是否允许用户自助注册。",
    ),
    SystemConfigDefault(
        key="auth.linuxdo_enabled",
        value_getter=lambda config: _bool_to_text(config.enable_linuxdo_login),
        description="是否启用 Linux.do OAuth 登录。",
    ),
    SystemConfigDefault(
        key="linuxdo.client_id",
        value_getter=lambda config: config.linuxdo_client_id,
        description="Linux.do OAuth Client ID。",
    ),
    SystemConfigDefault(
        key="linuxdo.client_secret",
        value_getter=lambda config: config.linuxdo_client_secret,
        description="Linux.do OAuth Client Secret。",
    ),
    SystemConfigDefault(
        key="linuxdo.redirect_uri",
        value_getter=lambda config: _to_optional_str(config.linuxdo_redirect_uri),
        description="Linux.do OAuth 回调地址。",
    ),
    SystemConfigDefault(
        key="linuxdo.auth_url",
        value_getter=lambda config: _to_optional_str(config.linuxdo_auth_url),
        description="Linux.do OAuth 授权地址。",
    ),
    SystemConfigDefault(
        key="linuxdo.token_url",
        value_getter=lambda config: _to_optional_str(config.linuxdo_token_url),
        description="Linux.do OAuth Token 获取地址。",
    ),
    SystemConfigDefault(
        key="linuxdo.user_info_url",
        value_getter=lambda config: _to_optional_str(config.linuxdo_user_info_url),
        description="Linux.do 用户信息接口地址。",
    ),
    SystemConfigDefault(
        key="writer.chapter_versions",
        value_getter=lambda config: _to_optional_str(config.writer_chapter_versions),
        description="每次生成章节的候选版本数量。",
    ),
    SystemConfigDefault(
        key="writer.models",
        value_getter=lambda _: None,
        description="写作模型列表（JSON数组），每个版本使用不同模型。例如：[\"provider1\", \"provider2\"]。留空则使用 nodes.writing 绑定的单一模型。",
    ),
    SystemConfigDefault(
        key="writer.min_words",
        value_getter=lambda config: _to_optional_str(config.writer_min_words),
        description="章节生成最小字数。",
    ),
    SystemConfigDefault(
        key="writer.max_words",
        value_getter=lambda config: _to_optional_str(config.writer_max_words),
        description="章节生成最大字数。",
    ),
    SystemConfigDefault(
        key="writer.score_threshold_early",
        value_getter=lambda _: "95",
        description="前三章的分数阈值（0-100），连续创作时低于此分数将触发重写。",
    ),
    SystemConfigDefault(
        key="writer.score_threshold_normal",
        value_getter=lambda _: "90",
        description="第四章及以后的分数阈值（0-100），连续创作时低于此分数将触发重写。",
    ),
    SystemConfigDefault(
        key="writer.max_rewrite_attempts",
        value_getter=lambda _: "3",
        description="连续创作时每章最大重写次数，超过后停止连续创作。",
    ),
    SystemConfigDefault(
        key="embedding.provider",
        value_getter=lambda config: config.embedding_provider,
        description="嵌入模型提供方，支持 openai 或 ollama。",
    ),
    SystemConfigDefault(
        key="embedding.api_key",
        value_getter=lambda config: config.embedding_api_key,
        description="嵌入模型专用 API Key，留空则使用默认 LLM API Key。",
    ),
    SystemConfigDefault(
        key="embedding.base_url",
        value_getter=lambda config: _to_optional_str(config.embedding_base_url),
        description="嵌入模型使用的 Base URL，留空则使用默认 LLM Base URL。",
    ),
    SystemConfigDefault(
        key="embedding.model",
        value_getter=lambda config: config.embedding_model,
        description="OpenAI 嵌入模型名称。",
    ),
    SystemConfigDefault(
        key="embedding.model_vector_size",
        value_getter=lambda config: _to_optional_str(config.embedding_model_vector_size),
        description="嵌入向量维度，留空则自动检测。",
    ),
    SystemConfigDefault(
        key="ollama.embedding_base_url",
        value_getter=lambda config: _to_optional_str(config.ollama_embedding_base_url),
        description="Ollama 嵌入模型服务地址。",
    ),
    SystemConfigDefault(
        key="ollama.embedding_model",
        value_getter=lambda config: config.ollama_embedding_model,
        description="Ollama 嵌入模型名称。",
    ),
]
