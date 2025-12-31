"""LLM 调用 Markdown 日志 Hook。

通过 pre/post hook 快速记录请求与响应，便于人工排查。
"""

from __future__ import annotations

import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from .encoding_fix import ensure_utf8_json

import logging

logger = logging.getLogger(__name__)

LOG_DIR_ENV = "ARBORIS_LLM_LOG_DIR"
DEFAULT_LOG_DIR = Path("logs") / "llm_calls"
_LOG_PATH_KEY = "_markdown_log_path"
_LOCK = threading.RLock()


def markdown_logging_pre_hook(
    messages: str | Sequence[Any], context: dict[str, Any] | None = None
) -> Sequence[Any] | str:
    """在调用前写入 Markdown 日志的 Prompt 部分。"""
    ctx = context or {}
    try:
        log_path = _write_prompt_log(messages, ctx)
        ctx[_LOG_PATH_KEY] = str(log_path)
    except Exception:  # pragma: no cover - 记录失败不阻断业务
        logger.exception("Failed to write LLM prompt log")
    return messages


def markdown_logging_post_hook(
    result: str, context: dict[str, Any] | None = None
) -> str:
    """在调用后写入响应部分，同时复用 UTF-8 JSON 修复逻辑。"""
    ctx = context or {}
    normalized = ensure_utf8_json(result, ctx)
    try:
        _append_response(normalized, ctx)
    except Exception:  # pragma: no cover - 记录失败不阻断业务
        logger.exception("Failed to append LLM response log")
    return normalized


def _write_prompt_log(messages: str | Sequence[Any], context: dict[str, Any]) -> Path:
    timestamp = datetime.now(timezone.utc)
    log_dir = _resolve_log_dir()
    agent_label = _describe_entity(context.get("from_agent"))
    filename = f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}_{_slugify(agent_label)}.md"
    log_path = log_dir / filename

    metadata_lines = _build_metadata_lines(timestamp, context)
    prompt_section = _render_messages(messages)
    body = "\n".join(
        [
            f"# LLM 调用日志 - {metadata_lines[0][1]}",
            "",
            "## 元信息",
            *[f"- {key}: {value}" for key, value in metadata_lines],
            "",
            "## Prompt",
            prompt_section if prompt_section else "_空_",
            "",
        ]
    )

    with _LOCK:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(body, encoding="utf-8")
    return log_path


def _append_response(result: str, context: dict[str, Any]) -> None:
    log_path_value = context.get(_LOG_PATH_KEY)
    if not log_path_value:
        return

    log_path = Path(log_path_value)
    response_block = "\n".join(
        [
            "## Response",
            "```text",
            result.strip(),
            "```",
            "",
        ]
    )
    with _LOCK:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if log_path.exists() else "w"
        with log_path.open(mode, encoding="utf-8") as handle:
            if mode == "w":
                logger.warning("Log path %s missing, rewriting full entry", log_path)
            handle.write(response_block)


def _render_messages(messages: str | Sequence[Any]) -> str:
    if isinstance(messages, str):
        return f"```text\n{messages.strip()}\n```"
    rendered: list[str] = []
    for idx, message in enumerate(messages or [], start=1):
        role = _extract_field(message, "role") or "message"
        content = _extract_field(message, "content") or str(message)
        rendered.append(
            "\n".join(
                [
                    f"### {idx}. {role}",
                    "```text",
                    content.strip(),
                    "```",
                    "",
                ]
            )
        )
    return "\n".join(rendered).rstrip()


def _build_metadata_lines(
    timestamp: datetime, context: dict[str, Any]
) -> list[tuple[str, str]]:
    tools = context.get("tools") or ()
    tool_names = _describe_tools(tools)
    return [
        ("Timestamp", timestamp.isoformat()),
        ("Agent", _describe_entity(context.get("from_agent")) or "N/A"),
        ("Task", _describe_entity(context.get("from_task")) or "N/A"),
        ("Model", context.get("model") or "N/A"),
        ("Provider", context.get("provider") or "N/A"),
        ("Base URL", context.get("base_url") or "N/A"),
        ("Tools", tool_names or "None"),
    ]


def _describe_entity(candidate: Any) -> str:
    if candidate is None:
        return ""
    if isinstance(candidate, str):
        return candidate
    for attr in ("name", "role", "key", "identifier", "title"):
        value = getattr(candidate, attr, None)
        if value:
            return str(value)
    if isinstance(candidate, dict):
        for key in ("name", "role", "key", "identifier", "title"):
            if key in candidate and candidate[key]:
                return str(candidate[key])
    return candidate.__class__.__name__


def _describe_tools(tools: Iterable[Any]) -> str:
    names: list[str] = []
    for tool in tools:
        if isinstance(tool, str):
            names.append(tool)
            continue
        if isinstance(tool, dict):
            label = tool.get("name") or tool.get("tool_name") or tool.get("type")
            if label:
                names.append(str(label))
                continue
        label = _describe_entity(tool)
        if label:
            names.append(label)
    return ", ".join(names)


def _extract_field(message: Any, field: str) -> str:
    if message is None:
        return ""
    if isinstance(message, dict):
        value = message.get(field)
        return str(value) if value is not None else ""
    value = getattr(message, field, None)
    if value is not None:
        return str(value)
    return ""


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", text or "llm")
    cleaned = cleaned.strip("-")
    return cleaned[:48] or "llm"


def _resolve_log_dir() -> Path:
    configured = os.getenv(LOG_DIR_ENV)
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_LOG_DIR


__all__ = ["markdown_logging_pre_hook", "markdown_logging_post_hook"]
