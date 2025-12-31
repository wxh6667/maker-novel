"""
LLM 调用重试工具模块

提供统一的重试逻辑，避免代码重复。
"""
import asyncio
import re
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# 默认重试配置
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFFS = [4, 8]  # 重试间隔：4秒、8秒
MAX_DELAY = 60  # 最大等待时间


def is_retryable_error(exc: Exception) -> bool:
    """判断是否为可重试的网络错误或API临时错误"""
    causes = [exc, getattr(exc, "__cause__", None)]
    for cause in causes:
        # 本地网络层错误
        if isinstance(cause, (httpx.RemoteProtocolError, httpx.ConnectError, httpx.TimeoutException)):
            return True
        # API 返回的可重试错误（408 超时、429 速率限制、502/503/504 服务器错误）
        if cause is not None:
            err_str = str(cause)
            if any(code in err_str for code in ["API Error 408", "API Error 429", "API Error 502", "API Error 503", "API Error 504"]):
                return True
    return False


def extract_retry_after(exc: Exception) -> Optional[int]:
    """从 429 错误中提取建议的等待时间"""
    causes = [exc, getattr(exc, "__cause__", None)]
    for cause in causes:
        if cause is not None:
            err_str = str(cause)
            # 匹配 "retry after X seconds" 或 "wait X seconds"
            match = re.search(r'(?:retry after|wait) (\d+) seconds?', err_str, re.IGNORECASE)
            if match:
                return int(match.group(1))
    return None


def calculate_retry_delay(exc: Exception, attempt: int, backoffs: list[int] = DEFAULT_BACKOFFS) -> int:
    """计算重试延迟时间"""
    # 优先使用 429 响应中的等待时间
    retry_after = extract_retry_after(exc)
    if retry_after is not None:
        delay = retry_after + 2  # 额外加 2 秒缓冲
    else:
        delay = backoffs[attempt] if attempt < len(backoffs) else backoffs[-1]
    # 限制最大等待时间
    return min(delay, MAX_DELAY)


async def retry_async_call(
    async_func,
    *args,
    context_name: str = "operation",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoffs: list[int] = DEFAULT_BACKOFFS,
    **kwargs,
):
    """
    通用异步重试包装器（用于非生成器函数）

    Args:
        async_func: 要执行的异步函数
        context_name: 用于日志的上下文名称
        max_attempts: 最大重试次数
        backoffs: 重试间隔列表
    """
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await async_func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if is_retryable_error(exc) and attempt < max_attempts - 1:
                delay = calculate_retry_delay(exc, attempt, backoffs)
                logger.warning(
                    "Call failed for %s (attempt %s/%s), retrying in %ss: %s",
                    context_name,
                    attempt + 1,
                    max_attempts,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
                continue
            raise

    # 不应该到达这里，但为了类型安全
    if last_exc:
        raise last_exc
