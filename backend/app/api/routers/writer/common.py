import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException

from ....schemas.novel import NovelProject as NovelProjectSchema
from ....services.novel_service import NovelService

logger = logging.getLogger(__name__)

# 统一创作锁管理（手动+自动互斥）
_creation_sessions: Dict[str, Dict[str, Any]] = {}
_creation_locks: Dict[str, asyncio.Lock] = {}
_LOCK_TTL_SECONDS = 30 * 60  # 锁超时时间：30分钟


def _get_lock(project_id: str) -> asyncio.Lock:
    """获取项目级别的锁，不存在则创建"""
    if project_id not in _creation_locks:
        _creation_locks[project_id] = asyncio.Lock()
    return _creation_locks[project_id]


def _is_lock_expired(state: Dict[str, Any]) -> bool:
    """检查锁是否已超时"""
    started_at = state.get("started_at")
    if not started_at:
        return False
    elapsed = (datetime.utcnow() - started_at).total_seconds()
    return elapsed > _LOCK_TTL_SECONDS


async def acquire_creation_lock(project_id: str, mode: str, user_id: int) -> None:
    """获取创作锁，若已有任务运行则抛出 409（超时锁自动清理）"""
    lock = _get_lock(project_id)
    async with lock:
        state = _creation_sessions.get(project_id)
        if state and state.get("running"):
            # 检查是否超时，超时则自动清理
            if _is_lock_expired(state):
                logger.warning(
                    "项目 %s 的创作锁已超时（%s），自动清理",
                    project_id, state.get("mode")
                )
                _creation_sessions.pop(project_id, None)
            else:
                raise HTTPException(status_code=409, detail="该项目有创作任务正在运行")
        _creation_sessions[project_id] = {
            "running": True,
            "mode": mode,
            "user_id": user_id,
            "cancel_requested": False,
            "started_at": datetime.utcnow(),
        }


async def release_creation_lock(project_id: str, expected_mode: str) -> None:
    """释放创作锁，仅匹配模式时释放"""
    lock = _get_lock(project_id)
    async with lock:
        state = _creation_sessions.get(project_id)
        if state and state.get("mode") == expected_mode:
            _creation_sessions.pop(project_id, None)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """截取章节结尾文本，默认保留 500 字。"""
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]
