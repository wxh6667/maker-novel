"""结构化输出校验工具。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Iterable

from json_repair import repair_json
from pydantic import BaseModel, ValidationError

from .encoding_fix import ensure_utf8_json


def _is_probable_json_start(source: str, idx: int) -> bool:
    """粗略判断当前位置是否可能是 JSON 起始。"""
    opener = source[idx]
    if opener not in "{[":
        return False

    j = idx + 1
    length = len(source)
    while j < length and source[j].isspace():
        j += 1

    if j >= length:
        return False

    nxt = source[j]
    if opener == "{":
        # 对象只能以 `"` 或 `}` 开头
        return nxt == '"' or nxt == "}"

    # 数组允许多种起始元素
    if nxt in ']"{[tf' or nxt in "0123456789-":
        return True
    if nxt == 'n':  # null
        return True
    return False


def _extract_balanced_json(source: str, start_idx: int) -> str | None:
    """从指定位置起，抽取首个配对完整的 JSON 片段。"""
    opener = source[start_idx]
    closer = "}" if opener == "{" else "]"
    stack: list[str] = [closer]
    in_string = False
    escape_next = False

    for idx in range(start_idx + 1, len(source)):
        ch = source[idx]

        if escape_next:
            escape_next = False
            continue

        if ch == "\\" and in_string:
            escape_next = True
            continue

        if ch == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
            continue

        if ch in "]}":
            if not stack or ch != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return source[start_idx:idx + 1]

    return None


def extract_json_block(source: str) -> str | None:
    """从任意文本中提取首个完整 JSON 对象/数组。"""
    in_string = False
    escape_next = False

    for idx, ch in enumerate(source):
        if escape_next:
            escape_next = False
            continue

        if ch == "\\" and in_string:
            escape_next = True
            continue

        if ch == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch in "{[" and _is_probable_json_start(source, idx):
            block = _extract_balanced_json(source, idx)
            if block:
                return block

    return None


def build_schema_hint(model: type[BaseModel]) -> str:
    """构建 JSON Schema 提示词。"""
    schema = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)
    return (
        "你必须严格输出单个 JSON 对象，字段只能来自以下 JSON Schema，"
        "禁止 Markdown/解释/代码围栏：\n"
        f"{schema}\n"
        "如遇校验失败会反馈错误信息，你必须立刻修正并重新输出。"
    )


def strip_code_fence(text: str) -> str:
    """移除 Markdown 代码围栏。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # remove leading fence line
        while lines and lines[0].lstrip().startswith("```"):
            lines.pop(0)
        # remove trailing fence line
        while lines and lines[-1].strip().startswith("```"):
            lines.pop()
        return "\n".join(lines).strip()
    return stripped


def normalize_json_payload(raw_text: str) -> str:
    """确保文本是合法的 JSON 字符串（移除围栏并修复）。"""
    cleaned = strip_code_fence(raw_text)
    # 优先执行 UTF-8 修复与 tidy
    sanitized = ensure_utf8_json(cleaned)

    extracted = extract_json_block(sanitized)
    candidate = extracted if extracted else sanitized

    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        repaired = repair_json(candidate)
        data = json.loads(repaired)
        return json.dumps(data, ensure_ascii=False)


def validate_against_model(
    response_model: type[BaseModel],
    raw_text: str,
) -> tuple[str, BaseModel]:
    """校验并解析结构化输出。"""
    normalized = normalize_json_payload(raw_text)
    instance = response_model.model_validate_json(normalized)
    serialized = json.dumps(instance.model_dump(), ensure_ascii=False, indent=2)
    return serialized, instance


def summarize_validation_error(exc: ValidationError) -> str:
    """汇总 Pydantic 校验错误。"""
    details: list[str] = []
    for item in exc.errors():
        loc = ".".join(str(part) for part in item.get("loc", ())) or "root"
        details.append(f"{loc}: {item.get('msg')}")
    return "; ".join(details) or str(exc)


def append_system_message(
    messages: Iterable[dict[str, Any]],
    content: str,
) -> list[dict[str, Any]]:
    """在消息列表末尾追加 system 消息。"""
    updated = [deepcopy(msg) for msg in messages]
    updated.append({"role": "system", "content": content})
    return updated


__all__ = [
    "append_system_message",
    "build_schema_hint",
    "normalize_json_payload",
    "strip_code_fence",
    "summarize_validation_error",
    "validate_against_model",
]
