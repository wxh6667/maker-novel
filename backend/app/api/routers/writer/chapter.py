import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.config import settings
from ....core.dependencies import get_current_user
from ....db.session import get_session
from ....schemas.novel import (
    ChapterGenerationStatus,
    DeleteChapterRequest,
    EditChapterRequest,
    GenerateChapterRequest,
    NovelProject as NovelProjectSchema,
    SelectVersionRequest,
)
from ....schemas.user import UserInDB
from ....services.chapter_context_service import ChapterContextService
from ....services.chapter_ingest_service import ChapterIngestionService
from ....services.llm_service import LLMService
from ....services.novel_service import NovelService
from ....services.prompt_service import PromptService
from ....services.vector_store_service import VectorStoreService
from ....utils.json_utils import remove_think_tags, unwrap_markdown_json, sanitize_json_like_text
from ....repositories.system_config_repository import SystemConfigRepository

from .common import (
    acquire_creation_lock,
    release_creation_lock,
    _load_project_schema,
    _extract_tail_excerpt,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
    _internal_call: bool = False,  # 内部调用时跳过锁
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("用户 %s 开始为项目 %s 生成第 %s 章", current_user.id, project_id, request.chapter_number)
    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        logger.warning("项目 %s 未找到第 %s 章纲要，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    # 获取创作锁（手动模式），内部调用时跳过
    if not _internal_call:
        await acquire_creation_lock(project_id, "manual", current_user.id)

    # 检查前一章是否已完成（第一章除外）
    if request.chapter_number > 1:
        prev_chapter = next(
            (ch for ch in project.chapters if ch.chapter_number == request.chapter_number - 1),
            None
        )
        if not prev_chapter or prev_chapter.status != "successful":
            prev_status = prev_chapter.status if prev_chapter else "不存在"
            logger.warning(
                "项目 %s 第 %s 章未完成(状态: %s)，拒绝生成第 %s 章",
                project_id, request.chapter_number - 1, prev_status, request.chapter_number
            )
            raise HTTPException(
                status_code=400,
                detail=f"请先完成第 {request.chapter_number - 1} 章（当前状态: {prev_status}）"
            )

    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    chapter.real_summary = None
    chapter.selected_version_id = None
    chapter.status = "generating"
    await session.commit()

    outlines_map = {item.chapter_number: item for item in project.outlines}
    # 收集所有可用的历史章节摘要，便于在 Prompt 中提供前情背景
    completed_chapters = []
    latest_prev_number = -1
    previous_summary_text = ""
    previous_tail_excerpt = ""
    for existing in project.chapters:
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue
        if not existing.real_summary:
            summary_chunks = []
            async for chunk in llm_service.stream_node(
                "summary",
                existing.selected_version.content,
                user_id=current_user.id,
            ):
                if chunk.get("content"):
                    summary_chunks.append(chunk["content"])
            existing.real_summary = remove_think_tags("".join(summary_chunks))
            await session.commit()
        completed_chapters.append(
            {
                "chapter_number": existing.chapter_number,
                "title": outlines_map.get(existing.chapter_number).title if outlines_map.get(existing.chapter_number) else f"第{existing.chapter_number}章",
                "summary": existing.real_summary,
            }
        )
        if existing.chapter_number > latest_prev_number:
            latest_prev_number = existing.chapter_number
            previous_summary_text = existing.real_summary or ""
            previous_tail_excerpt = _extract_tail_excerpt(existing.selected_version.content)

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")

    # 蓝图中禁止携带章节级别的细节信息，避免重复传输大段场景或对话内容
    banned_blueprint_keys = {
        "chapter_outline",
        "chapter_summaries",
        "chapter_details",
        "chapter_dialogues",
        "chapter_events",
        "conversation_history",
        "character_timelines",
    }
    for key in banned_blueprint_keys:
        if key in blueprint_dict:
            blueprint_dict.pop(key, None)

    writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        logger.error("未配置名为 'writing' 的写作提示词，无法生成章节内容")
        raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置 'writing' 提示词")

    # 读取字数限制配置并注入到 prompt（替换占位符）
    config_repo = SystemConfigRepository(session)
    min_words_config = await config_repo.get_by_key("writer.min_words")
    max_words_config = await config_repo.get_by_key("writer.max_words")
    min_words = int(min_words_config.value) if min_words_config and min_words_config.value else settings.writer_min_words
    max_words = int(max_words_config.value) if max_words_config and max_words_config.value else settings.writer_max_words
    writer_prompt = writer_prompt.replace("{{MIN_WORDS}}", str(min_words)).replace("{{MAX_WORDS}}", str(max_words))

    # 初始化向量检索服务，若未配置则自动降级为纯提示词生成
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，RAG 检索被禁用: %s", exc)
            vector_store = None
    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"
    query_parts = [outline_title, outline_summary]
    if request.writing_notes:
        query_parts.append(request.writing_notes)
    rag_query = "\n".join(part for part in query_parts if part)
    rag_context = await context_service.retrieve_for_generation(
        project_id=project_id,
        query_text=rag_query or outline.title or outline.summary or "",
        user_id=current_user.id,
    )
    chunk_count = len(rag_context.chunks) if rag_context and rag_context.chunks else 0
    summary_count = len(rag_context.summaries) if rag_context and rag_context.summaries else 0
    logger.debug(
        "项目 %s 第 %s 章检索到 %s 个剧情片段和 %s 条摘要",
        project_id,
        request.chapter_number,
        chunk_count,
        summary_count,
    )
    # print("rag_context:",rag_context)
    # 将蓝图、前情、RAG 检索结果拼装成结构化段落，供模型理解
    blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)
    completed_lines = [
        f"- 第{item['chapter_number']}章 - {item['title']}:{item['summary']}"
        for item in completed_chapters
    ]
    previous_summary_text = previous_summary_text or "暂无可用摘要"
    previous_tail_excerpt = previous_tail_excerpt or "暂无上一章结尾内容"
    completed_section = "\n".join(completed_lines) if completed_lines else "暂无前情摘要"
    rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context.chunks else "未检索到章节片段"
    rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context.summaries else "未检索到章节摘要"
    writing_notes = request.writing_notes or "无额外写作指令"

    prompt_sections = [
        ("[世界蓝图](JSON)", blueprint_text),
        # ("[前情摘要]", completed_section),
        ("[上一章摘要]", previous_summary_text),
        ("[上一章结尾]", previous_tail_excerpt),
        ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
        ("[检索到的章节摘要]", rag_summaries_text),
        (
            "[当前章节目标]",
            f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}",
        ),
    ]
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
    logger.debug("章节写作提示词：%s\n%s", writer_prompt, prompt_input)

    async def _generate_single_version(idx: int, provider_name: str, temperature: Optional[float]) -> Dict:
        """生成单个版本"""
        try:
            messages = [
                {"role": "system", "content": writer_prompt},
                {"role": "user", "content": prompt_input},
            ]
            logger.info(
                "项目 %s 第 %s 章第 %s 个版本使用模型: %s (温度: %s)",
                project_id,
                request.chapter_number,
                idx + 1,
                provider_name,
                temperature if temperature is not None else "默认",
            )
            # 使用流式调用避免服务器端超时
            chunks: list[str] = []
            async for chunk in llm_service.stream_with_provider(
                provider_name,
                messages,
                temperature_override=temperature,
            ):
                content = chunk.get("content")
                if content:
                    chunks.append(content)
            response = "".join(chunks)
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            sanitized = sanitize_json_like_text(normalized)
            try:
                result = json.loads(sanitized)
                result["_provider"] = provider_name
                # 获取模型信息
                try:
                    provider_config = llm_service.get_provider_config(provider_name)
                    if provider_config:
                        result["_model"] = provider_config.get("model", provider_name)
                except Exception:
                    result["_model"] = provider_name
                return result
            except json.JSONDecodeError as parse_err:
                logger.warning(
                    "项目 %s 第 %s 章第 %s 个版本 JSON 解析失败，将原始内容作为纯文本处理: %s, 内容前200字符: %s",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    parse_err,
                    sanitized[:200] if sanitized else "(空)",
                )
                # 获取模型信息
                model_name = provider_name
                try:
                    provider_config = llm_service.get_provider_config(provider_name)
                    if provider_config:
                        model_name = provider_config.get("model", provider_name)
                except Exception:
                    pass
                return {"content": sanitized, "_provider": provider_name, "_model": model_name}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "项目 %s 生成第 %s 章第 %s 个版本时发生异常: %s",
                project_id,
                request.chapter_number,
                idx + 1,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"生成章节第 {idx + 1} 个版本时失败: {str(exc)[:200]}"
            )

    # 读取写作模型配置
    writing_models = await _resolve_writing_models(session)

    # 检查是否配置了写作模型
    if not writing_models:
        raise HTTPException(
            status_code=400,
            detail="请先在设置页面配置写作模型"
        )

    version_count = len(writing_models)
    logger.info(
        "项目 %s 第 %s 章使用多模型写作，模型列表: %s",
        project_id,
        request.chapter_number,
        [item["name"] for item in writing_models],
    )

    # 并行生成版本
    tasks = [
        _generate_single_version(idx, item["name"], item["temperature"])
        for idx, item in enumerate(writing_models)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 过滤失败的结果
    raw_versions = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                "项目 %s 第 %s 章第 %s 个版本生成失败 (模型: %s): %s",
                project_id,
                request.chapter_number,
                idx + 1,
                writing_models[idx]["name"],
                result,
            )
        else:
            raw_versions.append(result)

    if not raw_versions:
        raise HTTPException(
            status_code=500,
            detail="所有版本生成均失败，请检查模型配置"
        )

    contents: List[str] = []
    metadata: List[Dict] = []
    for variant in raw_versions:
        if isinstance(variant, dict):
            if "content" in variant and isinstance(variant["content"], str):
                contents.append(variant["content"])
            elif "chapter_content" in variant:
                contents.append(str(variant["chapter_content"]))
            else:
                contents.append(json.dumps(variant, ensure_ascii=False))
            metadata.append(variant)
        else:
            contents.append(str(variant))
            metadata.append({"raw": variant})

    await novel_service.replace_chapter_versions(chapter, contents, metadata)
    logger.info(
        "项目 %s 第 %s 章生成完成，已写入 %s 个版本",
        project_id,
        request.chapter_number,
        len(contents),
    )
    # 释放创作锁（内部调用时跳过）
    if not _internal_call:
        await release_creation_lock(project_id, "manual")
    return await _load_project_schema(novel_service, project_id, current_user.id)


async def _resolve_version_count(session: AsyncSession) -> int:
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.chapter_versions")
    if record:
        try:
            value = int(record.value)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    env_value = os.getenv("WRITER_CHAPTER_VERSION_COUNT")
    if env_value:
        try:
            value = int(env_value)
            if value > 0:
                return value
        except ValueError:
            pass
    return 3


async def _resolve_writing_models(session: AsyncSession) -> List[Dict[str, Optional[float]]]:
    """
    读取 writer.models 配置，返回写作模型列表（包含温度）。
    如果未配置或配置无效，返回空列表。
    """
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.models")
    if record and record.value:
        try:
            models = json.loads(record.value)
            if isinstance(models, list):
                normalized: List[Dict[str, Optional[float]]] = []
                for item in models:
                    if isinstance(item, str):
                        if item:
                            normalized.append({"name": item, "temperature": None})
                        continue
                    if isinstance(item, dict):
                        name = item.get("name")
                        if not isinstance(name, str) or not name:
                            continue
                        temperature_value = item.get("temperature", None)
                        if temperature_value is None:
                            temperature = None
                        else:
                            try:
                                temperature = float(temperature_value)
                            except (TypeError, ValueError):
                                logger.warning(
                                    "writer.models 配置中的 temperature 无效: %s",
                                    temperature_value,
                                )
                                temperature = None
                        normalized.append({"name": name, "temperature": temperature})
                if normalized:
                    return normalized
        except (json.JSONDecodeError, TypeError):
            logger.warning("writer.models 配置格式无效")
    return []


@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法选择版本", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")

    selected = await novel_service.select_chapter_version(chapter, request.version_index)
    logger.debug(
        "用户 %s 选择了项目 %s 第 %s 章的第 %s 个版本",
        current_user.id,
        project_id,
        request.chapter_number,
        request.version_index,
    )
    if selected and selected.content:
        summary_chunks = []
        async for chunk in llm_service.stream_node(
            "summary",
            selected.content,
            user_id=current_user.id,
        ):
            if chunk.get("content"):
                summary_chunks.append(chunk["content"])
        chapter.real_summary = remove_think_tags("".join(summary_chunks))
        await session.commit()

        # 选定版本后同步向量库，确保后续章节可检索到最新内容
        vector_store: Optional[VectorStoreService]
        if not settings.vector_store_enabled:
            vector_store = None
        else:
            try:
                vector_store = VectorStoreService()
            except RuntimeError as exc:
                logger.warning("向量库初始化失败，跳过章节向量同步: %s", exc)
                vector_store = None

        if vector_store:
            ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
            outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
            chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
            await ingestion_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter.chapter_number,
                title=chapter_title,
                content=selected.content,
                summary=chapter.real_summary,
                user_id=current_user.id,
            )
            logger.debug(
                "项目 %s 第 %s 章已同步至向量库",
                project_id,
                chapter.chapter_number,
            )

    # 所有操作完成后，将状态设置为 SUCCESSFUL
    chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
    await session.commit()

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    if not request.chapter_numbers:
        logger.warning("项目 %s 删除章节时未提供章节号", project_id)
        raise HTTPException(status_code=400, detail="请提供要删除的章节号列表")
    novel_service = NovelService(session)
    llm_service = LLMService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 删除项目 %s 的章节 %s",
        current_user.id,
        project_id,
        request.chapter_numbers,
    )
    await novel_service.delete_chapters(project_id, request.chapter_numbers)

    # 删除章节时同步清理向量库，避免过时内容被检索
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量删除: %s", exc)
            vector_store = None

    if vector_store:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        await ingestion_service.delete_chapters(project_id, request.chapter_numbers)
        logger.debug(
            "项目 %s 已从向量库移除章节 %s",
            project_id,
            request.chapter_numbers,
        )

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter(
    project_id: str,
    request: EditChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter or chapter.selected_version is None:
        logger.warning("项目 %s 第 %s 章尚未生成或未选择版本，无法编辑", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节尚未生成或未选择版本")

    chapter.selected_version.content = request.content
    chapter.word_count = len(request.content)
    logger.debug("用户 %s 更新了项目 %s 第 %s 章内容", current_user.id, project_id, request.chapter_number)

    if request.content.strip():
        summary_chunks = []
        async for chunk in llm_service.stream_node(
            "summary",
            request.content,
            user_id=current_user.id,
        ):
            if chunk.get("content"):
                summary_chunks.append(chunk["content"])
        chapter.real_summary = remove_think_tags("".join(summary_chunks))
    await session.commit()

    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量更新: %s", exc)
            vector_store = None

    if vector_store and chapter.selected_version and chapter.selected_version.content:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
        chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
        await ingestion_service.ingest_chapter(
            project_id=project_id,
            chapter_number=chapter.chapter_number,
            title=chapter_title,
            content=chapter.selected_version.content,
            summary=chapter.real_summary,
            user_id=current_user.id,
        )
        logger.debug("项目 %s 第 %s 章更新内容已同步至向量库", project_id, chapter.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)
