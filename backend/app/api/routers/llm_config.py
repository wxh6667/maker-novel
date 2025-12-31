import json
import logging
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...repositories.system_config_repository import SystemConfigRepository
from ...schemas.llm_config import (
    ProviderCreate,
    ProviderRead,
    ProviderListResponse,
)
from ...schemas.user import UserInDB
from ...services.llm_service import LLMService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm-config", tags=["LLM Configuration"])


def get_llm_service(session: AsyncSession = Depends(get_session)) -> LLMService:
    return LLMService(session)


# ============ 节点绑定 API ============

@router.get("/nodes", response_model=Dict[str, str])
async def get_node_bindings(
    service: LLMService = Depends(get_llm_service),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, str]:
    """获取所有节点绑定。"""
    logger.debug("用户 %s 获取节点绑定", current_user.id)
    return service.get_node_bindings()


@router.put("/nodes/{node}", response_model=Dict[str, str])
async def set_node_binding(
    node: str,
    provider_name: str = Body(..., embed=True),
    service: LLMService = Depends(get_llm_service),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, str]:
    """设置节点绑定。"""
    logger.info("用户 %s 设置节点 %s 绑定为 %s", current_user.id, node, provider_name)
    try:
        service.set_node_binding(node, provider_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return service.get_node_bindings()


@router.get("/providers")
async def get_available_providers(
    service: LLMService = Depends(get_llm_service),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, list]:
    """获取所有可用的 Provider。"""
    logger.debug("用户 %s 获取可用 Provider 列表", current_user.id)
    return {"providers": service.get_available_providers()}


# ============ Provider 管理 API ============

@router.get("/providers/details", response_model=ProviderListResponse)
async def get_all_providers(
    service: LLMService = Depends(get_llm_service),
    current_user: UserInDB = Depends(get_current_user),
) -> ProviderListResponse:
    """获取所有 Provider 的详细配置。"""
    logger.debug("用户 %s 获取所有 Provider 详细配置", current_user.id)
    configs = service.get_all_provider_configs()
    return ProviderListResponse(
        providers=[ProviderRead(**c) for c in configs]
    )


@router.post("/providers", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate,
    service: LLMService = Depends(get_llm_service),
    current_user: UserInDB = Depends(get_current_user),
) -> ProviderRead:
    """创建新的 Provider 配置。"""
    # 检查是否已存在
    existing = service.get_provider_config(payload.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Provider {payload.name} 已存在"
        )
    logger.info("用户 %s 创建 Provider: %s", current_user.id, payload.name)
    result = service.add_provider(
        name=payload.name,
        model=payload.model,
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=payload.api_key,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        timeout=payload.timeout,
        support_json_mode=payload.support_json_mode,
        support_stream=payload.support_stream,
        proxy=payload.proxy,
        embed_api_type=payload.embed_api_type,
    )
    return ProviderRead(**result)


@router.put("/providers/{name}", response_model=ProviderRead)
async def update_provider(
    name: str,
    payload: ProviderCreate,
    service: LLMService = Depends(get_llm_service),
    current_user: UserInDB = Depends(get_current_user),
) -> ProviderRead:
    """更新 Provider 配置。"""
    logger.info("用户 %s 更新 Provider: %s", current_user.id, name)
    try:
        result = service.update_provider(
            name=name,
            model=payload.model,
            provider=payload.provider,
            base_url=payload.base_url,
            api_key=payload.api_key,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            timeout=payload.timeout,
            support_json_mode=payload.support_json_mode,
            support_stream=payload.support_stream,
            proxy=payload.proxy,
            embed_api_type=payload.embed_api_type,
        )
        return ProviderRead(**result)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/providers/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    name: str,
    service: LLMService = Depends(get_llm_service),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """删除 Provider 配置。"""
    logger.info("用户 %s 删除 Provider: %s", current_user.id, name)
    deleted = service.remove_provider(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Provider {name} 不存在")


@router.post("/providers/{name}/test")
async def test_provider_connection(
    name: str,
    service: LLMService = Depends(get_llm_service),
    current_user: UserInDB = Depends(get_current_user),
):
    """测试 Provider 连接是否可用。"""
    logger.debug("用户 %s 测试 Provider 连接: %s", current_user.id, name)
    return await service.test_provider_connection(name)


@router.post("/providers/{name}/test-json")
async def test_provider_json_mode(
    name: str,
    service: LLMService = Depends(get_llm_service),
    current_user: UserInDB = Depends(get_current_user),
):
    """测试 Provider 是否支持 JSON 模式输出。"""
    logger.debug("用户 %s 测试 Provider JSON 模式: %s", current_user.id, name)
    return await service.test_provider_json_mode(name)


# ============ 写作模型配置 API ============

class WritingModelItem(BaseModel):
    """写作模型条目配置。"""
    name: str
    temperature: Optional[float] = None
    revision_temperature: Optional[float] = 0.3  # 修订任务温度，默认0.3


class WritingModelsRequest(BaseModel):
    """写作模型配置请求。"""
    models: List[Union[WritingModelItem, str, dict]]


class WritingModelsResponse(BaseModel):
    """写作模型配置响应。"""
    models: List[WritingModelItem]


def _normalize_writing_models(items: List) -> List[WritingModelItem]:
    """将各种格式的写作模型配置统一转换为 WritingModelItem 列表。"""
    normalized: List[WritingModelItem] = []
    for item in items:
        if isinstance(item, WritingModelItem):
            normalized.append(item)
            continue
        if isinstance(item, str):
            if item:
                normalized.append(WritingModelItem(name=item))
            continue
        if isinstance(item, dict):
            name = item.get("name")
            if not isinstance(name, str) or not name:
                continue
            temperature_value = item.get("temperature")
            revision_temp_value = item.get("revision_temperature")

            temp = None
            if temperature_value is not None:
                try:
                    temp = float(temperature_value)
                except (TypeError, ValueError):
                    pass

            rev_temp = 0.3  # 默认值
            if revision_temp_value is not None:
                try:
                    rev_temp = float(revision_temp_value)
                except (TypeError, ValueError):
                    pass

            normalized.append(WritingModelItem(
                name=name,
                temperature=temp,
                revision_temperature=rev_temp
            ))
    return normalized


@router.get("/writing-models", response_model=WritingModelsResponse)
async def get_writing_models(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> WritingModelsResponse:
    """获取已选的写作模型列表。"""
    logger.debug("用户 %s 获取写作模型配置", current_user.id)
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.models")
    if record and record.value:
        try:
            models = json.loads(record.value)
            if isinstance(models, list):
                normalized = _normalize_writing_models(models)
                if normalized:
                    return WritingModelsResponse(models=normalized)
        except (json.JSONDecodeError, TypeError):
            logger.warning("writer.models 配置格式无效")
    return WritingModelsResponse(models=[])


@router.put("/writing-models", response_model=WritingModelsResponse)
async def set_writing_models(
    payload: WritingModelsRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> WritingModelsResponse:
    """保存写作模型多选配置。"""
    logger.info("用户 %s 设置写作模型配置: %s", current_user.id, payload.models)
    repo = SystemConfigRepository(session)
    normalized = _normalize_writing_models(payload.models)
    value = json.dumps([item.model_dump() for item in normalized], ensure_ascii=False)
    await repo.upsert("writer.models", value)
    await session.commit()
    return WritingModelsResponse(models=normalized)


# ============ 分数阈值配置 API ============

class ScoreThresholdConfig(BaseModel):
    """分数阈值配置。"""
    score_threshold_early: int = 95  # 前三章阈值
    score_threshold_normal: int = 90  # 后续章节阈值
    max_rewrite_attempts: int = 3  # 最大重写次数


@router.get("/score-thresholds", response_model=ScoreThresholdConfig)
async def get_score_thresholds(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ScoreThresholdConfig:
    """获取分数阈值配置。"""
    logger.debug("用户 %s 获取分数阈值配置", current_user.id)
    repo = SystemConfigRepository(session)

    early_record = await repo.get_by_key("writer.score_threshold_early")
    normal_record = await repo.get_by_key("writer.score_threshold_normal")
    attempts_record = await repo.get_by_key("writer.max_rewrite_attempts")

    return ScoreThresholdConfig(
        score_threshold_early=int(early_record.value) if early_record and early_record.value else 95,
        score_threshold_normal=int(normal_record.value) if normal_record and normal_record.value else 90,
        max_rewrite_attempts=int(attempts_record.value) if attempts_record and attempts_record.value else 3,
    )


@router.put("/score-thresholds", response_model=ScoreThresholdConfig)
async def set_score_thresholds(
    payload: ScoreThresholdConfig,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ScoreThresholdConfig:
    """保存分数阈值配置。"""
    logger.info(
        "用户 %s 设置分数阈值配置: early=%s, normal=%s, max_attempts=%s",
        current_user.id,
        payload.score_threshold_early,
        payload.score_threshold_normal,
        payload.max_rewrite_attempts,
    )
    repo = SystemConfigRepository(session)

    await repo.upsert("writer.score_threshold_early", str(payload.score_threshold_early))
    await repo.upsert("writer.score_threshold_normal", str(payload.score_threshold_normal))
    await repo.upsert("writer.max_rewrite_attempts", str(payload.max_rewrite_attempts))
    await session.commit()

    return payload
