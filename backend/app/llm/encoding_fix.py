"""编码修复工具 - 自动修复 OpenAI 返回的乱码中文。

问题根源：
当使用代理服务器时，HTTP响应的 Content-Type 可能声明为 charset=utf-8,
但实际字节流可能被中间件错误处理，导致 UTF-8 字节被解释为 Latin-1或其他编码。

典型乱码模式：
- "章节规划" → "é£é¨ç¨"å¤ç°"
- "第一章" → "ç¬¬ä¸€ç«"
- 原因：UTF-8 三字节序列（如 E7 AB A0）被当作三个 Latin-1 字符

修复策略：
1. 检测是否存在乱码（通过正则匹配非ASCII Latin-1字符）
2. 尝试 Latin-1 → bytes → UTF-8 重新解码
3. 保留JSON结构完整性
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def detect_garbled_chinese(text: str) -> bool:
    """检测文本是否包含乱码中文字符。

    乱码特征：包含大量的 Latin-1 扩展字符（0x80-0xFF 范围）
    """
    # 统计非ASCII Latin-1字符的比例
    latin1_extended = sum(1 for c in text if 0x80 <= ord(c) < 0x100)

    if len(text) == 0:
        return False

    # 如果超过10%的字符是Latin-1扩展字符，可能是乱码
    ratio = latin1_extended / len(text)

    # 也检查特定的乱码模式（UTF-8的"章"= E7 AB A0 → Latin-1的 "ç «  ")
    garbled_patterns = [
        r"[À-ÿ]{2,}",  # 连续的Latin-1扩展字符
        r"ç«|é|å|ä|è",  # 常见的中文乱码片段
    ]

    pattern_match = any(re.search(p, text) for p in garbled_patterns)

    is_garbled = ratio > 0.1 or pattern_match

    if is_garbled:
        logger.debug(f"Detected garbled text (Latin-1 ratio: {ratio:.2%})")

    return is_garbled


def fix_garbled_chinese(text: str, context: dict[str, Any] | None = None) -> str:
    """修复乱码的中文文本（用作 post_hook）。

    Args:
        text: 可能包含乱码的响应文本
        context: 上下文信息（未使用）

    Returns:
        修复后的文本
    """
    if not text:
        return text

    # 首先处理 surrogate characters（Windows 控制台问题）
    try:
        # 移除 surrogate characters
        text = text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")
    except Exception:
        pass

    if not detect_garbled_chinese(text):
        return text

    logger.warning(
        "Detected garbled Chinese characters, attempting to fix encoding..."
    )

    try:
        # 策略1：Latin-1 → bytes → UTF-8
        # 假设：原始UTF-8字节被错误地解释为Latin-1字符
        fixed = text.encode("latin-1", errors="replace").decode("utf-8", errors="replace")
        logger.debug("Successfully fixed encoding (Latin-1 → UTF-8)")

        # 验证修复效果：检查是否还有乱码
        if detect_garbled_chinese(fixed):
            logger.warning("Encoding fix may be incomplete")

        return fixed

    except (UnicodeDecodeError, UnicodeEncodeError) as e:
        logger.error(f"Failed to fix encoding: {e}")
        logger.debug(f"Problematic text sample: {text[:200]}")

        # 无法修复，返回原文
        return text


def sanitize_json_control_chars(text: str) -> str:
    """清理 JSON 字符串中的控制字符。

    JSON 规范要求字符串中的控制字符（\\u0000-\\u001F）必须使用转义序列。
    LLM 输出有时会包含未转义的换行符、制表符等，导致解析失败。

    策略：
    1. 在 JSON 字符串值内部，将控制字符替换为转义序列
    2. 保留正常的 JSON 结构换行
    """
    result = []
    in_string = False
    escape_next = False

    for char in text:
        if escape_next:
            result.append(char)
            escape_next = False
            continue

        if char == '\\' and in_string:
            result.append(char)
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            result.append(char)
            continue

        # 在字符串内部处理控制字符
        if in_string and ord(char) < 0x20:
            # 替换为转义序列
            if char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            else:
                # 其他控制字符用 Unicode 转义
                result.append(f'\\u{ord(char):04x}')
        else:
            result.append(char)

    return ''.join(result)


def ensure_utf8_json(text: str, context: dict[str, Any] | None = None) -> str:
    """确保JSON输出使用UTF-8编码且不转义Unicode。

    用作 post_hook，在返回结果前自动修复编码并规范化JSON。
    """
    # 先修复可能的乱码
    fixed_text = fix_garbled_chinese(text, context)

    # 移除代码围栏
    stripped = fixed_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            # 移除首尾的 ```json 和 ```
            stripped = "\n".join(lines[1:-1]).strip()

    # 清理控制字符
    stripped = sanitize_json_control_chars(stripped)

    # 尝试解析并重新序列化，确保使用 ensure_ascii=False
    try:
        data = json.loads(stripped)
        # 重新序列化，强制使用 UTF-8 且不转义
        normalized = json.dumps(data, ensure_ascii=False, indent=2)
        logger.debug("JSON normalized with ensure_ascii=False")
        return normalized
    except json.JSONDecodeError:
        # 不是有效JSON，返回修复后的文本
        return fixed_text


def diagnose_encoding(text: str) -> dict[str, Any]:
    """诊断文本的编码问题。

    Returns:
        诊断信息字典
    """
    info: dict[str, Any] = {
        "length": len(text),
        "has_garbled": detect_garbled_chinese(text),
        "encodings": {},
        "sample": text[:100],
    }

    # 尝试检测可能的编码
    encodings_to_try = ["utf-8", "latin-1", "gbk", "gb2312"]

    for enc in encodings_to_try:
        try:
            # 尝试编码再解码
            text.encode(enc).decode(enc)
            info["encodings"][enc] = "OK"
        except (UnicodeDecodeError, UnicodeEncodeError) as e:
            info["encodings"][enc] = f"Error: {str(e)}"

    return info


__all__ = [
    "fix_garbled_chinese",
    "ensure_utf8_json",
    "detect_garbled_chinese",
    "diagnose_encoding",
    "sanitize_json_control_chars",
]
