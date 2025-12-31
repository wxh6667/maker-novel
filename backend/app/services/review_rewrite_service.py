"""
评审-重写循环服务

流程：
1. 生成章节内容（多版本）
2. AI 评审打分
3. 检查分数是否达标
4. 不达标则带反馈重新生成（最多 N 次）
5. 返回最终结果
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..repositories.system_config_repository import SystemConfigRepository
from ..schemas.review import (
    ChapterReviewResult,
    DetailedWeakness,
    GenerateWithReviewRequest,
    GenerateWithReviewResponse,
    ReviewRewriteState,
    ReviewStatus,
)
from ..services.chapter_context_service import ChapterContextService
from ..services.llm_service import LLMService
from ..services.novel_service import NovelService
from ..services.prompt_service import PromptService
from ..services.vector_store_service import VectorStoreService
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json, sanitize_json_like_text

logger = logging.getLogger(__name__)

_EVALUATION_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "evaluation_detailed.md"


def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """提取文本末尾片段"""
    if not text:
        return ""
    stripped = text.strip()
    return stripped if len(stripped) <= limit else stripped[-limit:]


class ReviewRewriteService:
    """评审-重写循环服务"""

    def __init__(
        self,
        session: AsyncSession,
        llm_service: LLMService,
        novel_service: NovelService,
        prompt_service: PromptService,
    ) -> None:
        self.session = session
        self.llm_service = llm_service
        self.novel_service = novel_service
        self.prompt_service = prompt_service

    async def generate_with_review(
        self,
        *,
        project_id: str,
        user_id: int,
        request: GenerateWithReviewRequest,
    ) -> GenerateWithReviewResponse:
        """
        带评审的生成流程

        循环：生成 → 评审 → 检查分数 → 决定是否重写
        """
        # 优先使用请求参数，否则从数据库读取配置
        config_repo = SystemConfigRepository(self.session)

        # 分数阈值：优先使用请求参数
        if request.score_threshold is not None and request.score_threshold > 0:
            score_threshold = request.score_threshold
        else:
            early_threshold_record = await config_repo.get_by_key("writer.score_threshold_early")
            normal_threshold_record = await config_repo.get_by_key("writer.score_threshold_normal")
            score_threshold_early = int(early_threshold_record.value) if early_threshold_record and early_threshold_record.value else 95
            score_threshold_normal = int(normal_threshold_record.value) if normal_threshold_record and normal_threshold_record.value else 90
            score_threshold = score_threshold_early if request.chapter_number <= 3 else score_threshold_normal

        # 最大尝试次数：优先使用请求参数
        if request.max_attempts is not None and request.max_attempts > 0:
            max_rewrite_attempts = request.max_attempts
        else:
            max_attempts_record = await config_repo.get_by_key("writer.max_rewrite_attempts")
            max_rewrite_attempts = int(max_attempts_record.value) if max_attempts_record and max_attempts_record.value else 3

        state = ReviewRewriteState(
            attempt=0,
            max_attempts=max_rewrite_attempts,
            score_threshold=score_threshold,
        )
        best_version_index = -1

        # 只保留上一轮的数据（不累积）
        last_round_weaknesses: dict[str, List[DetailedWeakness]] = {}
        last_round_contents: dict[str, str] = {}
        last_round_pros: dict[str, List[str]] = {}

        for attempt in range(1, state.max_attempts + 1):
            state.attempt = attempt
            logger.info(
                "项目 %s 第 %s 章：第 %s/%s 次生成",
                project_id,
                request.chapter_number,
                attempt,
                state.max_attempts,
            )

            # 1. 生成章节内容（传入上一轮的缺点和内容）
            generated_contents = await self._generate_chapter_internal(
                project_id=project_id,
                user_id=user_id,
                chapter_number=request.chapter_number,
                writing_notes=request.writing_notes,
                rewrite_provider=request.rewrite_provider,
                provider_weaknesses=last_round_weaknesses,
                provider_last_contents=last_round_contents,
                provider_pros=last_round_pros,
            )

            # 2. 评审
            review = await self._evaluate_chapter_internal(
                project_id=project_id,
                user_id=user_id,
                chapter_number=request.chapter_number,
            )
            state.review_history.append(review)

            # 3. 获取最佳版本信息并收集本轮缺点（替换上一轮，不累积）
            best_choice = max(review.best_choice, 1)
            best_version_index = best_choice - 1
            score = 0

            # 获取当前章节的版本信息，用于关联 provider
            project = await self.novel_service.ensure_project_owner(project_id, user_id)
            chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
            versions_list = sorted(chapter.versions, key=lambda v: v.created_at) if chapter and chapter.versions else []

            # 本轮的缺点（替换上一轮）
            current_round_weaknesses: dict[str, List[DetailedWeakness]] = {}
            current_round_pros: dict[str, List[str]] = {}

            for version in review.versions:
                # 获取该版本对应的 provider
                version_idx = version.version_index - 1
                provider_name = versions_list[version_idx].provider if version_idx < len(versions_list) else None

                if provider_name:
                    if version.cons:
                        current_round_weaknesses[provider_name] = version.cons
                    if version.pros:
                        current_round_pros[provider_name] = version.pros

                if version.version_index == best_choice:
                    score = version.score

            state.current_score = int(score or 0)

            # 更新上一轮数据为本轮数据（替换而非累积）
            last_round_weaknesses = current_round_weaknesses
            last_round_contents = generated_contents
            last_round_pros = current_round_pros

            # 统一的缺点（用于返回给前端展示）
            all_weaknesses = []
            for weaknesses in current_round_weaknesses.values():
                all_weaknesses.extend(weaknesses)
            state.accumulated_weaknesses = self._deduplicate_weaknesses(all_weaknesses)

            logger.info(
                "项目 %s 第 %s 章：第 %s 次评审完成，最高分 %s（阈值 %s），各模型缺点数: %s",
                project_id,
                request.chapter_number,
                attempt,
                state.current_score,
                state.score_threshold,
                {k: len(v) for k, v in current_round_weaknesses.items()},
            )

            # 5. 检查是否达标
            if state.current_score >= state.score_threshold:
                state.status = ReviewStatus.PASSED
                logger.info(
                    "项目 %s 第 %s 章：分数达标，流程结束",
                    project_id,
                    request.chapter_number,
                )
                break

            state.status = ReviewStatus.NEEDS_REWRITE
            if attempt == state.max_attempts:
                state.status = ReviewStatus.MAX_ATTEMPTS
                logger.warning(
                    "项目 %s 第 %s 章：已达最大尝试次数 %s，使用当前最佳版本",
                    project_id,
                    request.chapter_number,
                    state.max_attempts,
                )

        # 6. 自动选择最佳版本
        if request.auto_select_best and best_version_index >= 0:
            project = await self.novel_service.ensure_project_owner(project_id, user_id)
            chapter = next(
                (ch for ch in project.chapters if ch.chapter_number == request.chapter_number),
                None,
            )
            if chapter:
                await self.novel_service.select_chapter_version(chapter, best_version_index)

        return GenerateWithReviewResponse(
            success=state.status == ReviewStatus.PASSED,
            final_score=state.current_score,
            attempts_used=state.attempt,
            status=state.status,
            best_version_index=best_version_index if best_version_index >= 0 else 0,
            review_history=state.review_history,
            accumulated_feedback=state.accumulated_weaknesses,
        )

    async def _generate_chapter_internal(
        self,
        *,
        project_id: str,
        user_id: int,
        chapter_number: int,
        writing_notes: Optional[str] = None,
        rewrite_provider: Optional[str] = None,
        provider_weaknesses: Optional[dict[str, List[DetailedWeakness]]] = None,
        provider_last_contents: Optional[dict[str, str]] = None,
        provider_pros: Optional[dict[str, List[str]]] = None,
    ) -> dict[str, str]:
        """
        内部生成方法

        复用 writer.py 中的生成逻辑，支持按模型注入历史缺点、优点和上一轮内容
        返回本轮各模型生成的内容 {provider: content}
        """
        project = await self.novel_service.ensure_project_owner(project_id, user_id)
        outline = await self.novel_service.get_outline(project_id, chapter_number)
        if not outline:
            raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

        chapter = await self.novel_service.get_or_create_chapter(project_id, chapter_number)
        rewrite_target_index: Optional[int] = None
        existing_versions = []
        if rewrite_provider:
            existing_versions = sorted(chapter.versions, key=lambda item: item.created_at) if chapter.versions else []
            if not existing_versions:
                raise HTTPException(status_code=400, detail="当前章节没有可重写的版本")
            for idx, version in enumerate(existing_versions):
                if version.provider == rewrite_provider:
                    rewrite_target_index = idx
                    if provider_last_contents is None:
                        provider_last_contents = {}
                    if rewrite_provider not in provider_last_contents:
                        provider_last_contents = dict(provider_last_contents)
                        provider_last_contents[rewrite_provider] = version.content or ""
                    break
            if rewrite_target_index is None:
                raise HTTPException(status_code=400, detail="未找到指定模型的版本")

        chapter.real_summary = None
        chapter.selected_version_id = None
        chapter.status = "generating"
        await self.session.commit()

        # 收集前序章节信息
        latest_prev_number = -1
        previous_summary_text = ""
        previous_tail_excerpt = ""

        for existing in project.chapters:
            if existing.chapter_number >= chapter_number:
                continue
            if existing.selected_version is None or not existing.selected_version.content:
                continue
            if not existing.real_summary:
                summary_chunks = []
                async for chunk in self.llm_service.stream_node(
                    "outline",
                    existing.selected_version.content,
                    user_id=user_id,
                ):
                    if chunk.get("content"):
                        summary_chunks.append(chunk["content"])
                existing.real_summary = remove_think_tags("".join(summary_chunks))
                await self.session.commit()
            if existing.chapter_number > latest_prev_number:
                latest_prev_number = existing.chapter_number
                previous_summary_text = existing.real_summary or ""
                previous_tail_excerpt = _extract_tail_excerpt(existing.selected_version.content)

        # 构建蓝图
        project_schema = await self.novel_service._serialize_project(project)
        blueprint_dict = project_schema.blueprint.model_dump()

        if blueprint_dict.get("relationships"):
            for relation in blueprint_dict["relationships"]:
                if "character_from" in relation:
                    relation["from"] = relation.pop("character_from")
                if "character_to" in relation:
                    relation["to"] = relation.pop("character_to")

        # 移除章节级别细节
        for key in {
            "chapter_outline",
            "chapter_summaries",
            "chapter_details",
            "chapter_dialogues",
            "chapter_events",
            "conversation_history",
            "character_timelines",
        }:
            blueprint_dict.pop(key, None)

        # 获取写作提示词
        writer_prompt = await self.prompt_service.get_prompt("writing")
        if not writer_prompt:
            raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置 'writing' 提示词")

        # 获取修订提示词（用于重写任务）
        revision_prompt = await self.prompt_service.get_prompt("revision")

        # 读取字数配置
        config_repo = SystemConfigRepository(self.session)
        min_words_config = await config_repo.get_by_key("writer.min_words")
        max_words_config = await config_repo.get_by_key("writer.max_words")
        min_words = (
            int(min_words_config.value)
            if min_words_config and min_words_config.value
            else settings.writer_min_words
        )
        max_words = (
            int(max_words_config.value)
            if max_words_config and max_words_config.value
            else settings.writer_max_words
        )
        writer_prompt = writer_prompt.replace("{{MIN_WORDS}}", str(min_words)).replace("{{MAX_WORDS}}", str(max_words))

        # 修订提示词也需要替换字数变量
        if revision_prompt:
            revision_prompt = revision_prompt.replace("{{MIN_WORDS}}", str(min_words)).replace("{{MAX_WORDS}}", str(max_words))

        # 初始化向量检索
        vector_store = None
        if settings.vector_store_enabled:
            try:
                vector_store = VectorStoreService()
            except RuntimeError:
                vector_store = None

        context_service = ChapterContextService(llm_service=self.llm_service, vector_store=vector_store)

        # RAG 检索
        outline_title = outline.title or f"第{outline.chapter_number}章"
        outline_summary = outline.summary or "暂无摘要"
        query_parts = [outline_title, outline_summary]
        if writing_notes:
            query_parts.append(writing_notes)
        rag_query = "\n".join(part for part in query_parts if part)

        rag_context = await context_service.retrieve_for_generation(
            project_id=project_id,
            query_text=rag_query or outline_title or outline_summary or "",
            user_id=user_id,
        )

        # 构建提示词
        blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)
        previous_summary_text = previous_summary_text or "暂无可用摘要"
        previous_tail_excerpt = previous_tail_excerpt or "暂无上一章结尾内容"
        rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context.chunks else "未检索到章节片段"
        rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context.summaries else "未检索到章节摘要"
        # 首次生成使用用户的写作指令，修订任务则由评审反馈自动引导
        writing_notes_text = writing_notes or "无额外写作指令"

        prompt_sections = [
            ("[世界蓝图](JSON)", blueprint_text),
            ("[上一章摘要]", previous_summary_text),
            ("[上一章结尾]", previous_tail_excerpt),
            ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
            ("[检索到的章节摘要]", rag_summaries_text),
            ("[当前章节目标]", f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes_text}"),
        ]
        # 修订任务专用：不含用户写作指令，由评审反馈引导
        revision_prompt_sections = [
            ("[世界蓝图](JSON)", blueprint_text),
            ("[上一章摘要]", previous_summary_text),
            ("[上一章结尾]", previous_tail_excerpt),
            ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
            ("[检索到的章节摘要]", rag_summaries_text),
            ("[当前章节目标]", f"标题：{outline_title}\n摘要：{outline_summary}"),
        ]

        # 基础提示词（不含缺点）
        base_prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
        # 修订任务专用基础提示词
        revision_base_prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in revision_prompt_sections if content)

        async def _generate_single_version(idx: int, provider_name: str) -> dict:
            """生成单个版本"""
            try:
                # 【关键】为每个模型注入其对应的缺点、优点和上一轮内容
                current_prompt = base_prompt_input
                revision_parts = []

                # 检查是否有修订内容
                has_last_content = provider_last_contents and provider_name in provider_last_contents and provider_last_contents[provider_name]
                has_pros = provider_pros and provider_name in provider_pros and provider_pros[provider_name]
                has_cons = provider_weaknesses and provider_name in provider_weaknesses and provider_weaknesses[provider_name]

                if has_last_content or has_pros or has_cons:
                    # 修订任务：只注入必要的动态数据，指令部分由 revision.md 系统提示词承担

                    # 注入上一轮内容
                    if has_last_content:
                        last_content = provider_last_contents[provider_name]
                        revision_parts.append(f"[上一版本内容]\n```\n{last_content}\n```")

                    # 注入上一轮优点（需要保持）
                    if has_pros:
                        pros = provider_pros[provider_name]
                        pros_text = "\n".join(f"- {p}" for p in pros)
                        revision_parts.append(f"[上一版本优点]\n{pros_text}")

                    # 注入上一轮缺点（需要改进）
                    if has_cons:
                        issues = provider_weaknesses[provider_name]
                        revision_parts.append(f"[上一版本问题]\n{self._format_avoid_issues(issues)}")

                    # 修订数据 + 背景信息
                    revision_section = "\n\n".join(revision_parts)
                    current_prompt = revision_section + "\n\n---\n\n" + revision_base_prompt_input

                    logger.debug(
                        "模型 %s 注入上一轮内容(%d字) + %d 条优点 + %d 条缺点",
                        provider_name,
                        len(provider_last_contents.get(provider_name, "")) if provider_last_contents else 0,
                        len(provider_pros.get(provider_name, [])) if provider_pros else 0,
                        len(provider_weaknesses.get(provider_name, [])) if provider_weaknesses else 0,
                    )

                # 选择使用修订提示词还是写作提示词
                is_revision = has_last_content or has_pros or has_cons
                system_prompt = revision_prompt if (is_revision and revision_prompt) else writer_prompt

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": current_prompt},
                ]
                response_chunks = []

                # 修订任务使用配置的温度，首次创作使用默认温度
                temperature = model_revision_temps.get(provider_name, 0.3) if is_revision else None

                async for chunk in self.llm_service.stream_with_provider(
                    provider_name,
                    messages,
                    temperature_override=temperature,
                ):
                    if chunk.get("content"):
                        response_chunks.append(chunk["content"])
                response = "".join(response_chunks)
                cleaned = remove_think_tags(response)
                normalized = unwrap_markdown_json(cleaned)
                sanitized = sanitize_json_like_text(normalized)
                try:
                    result = json.loads(sanitized)
                    result["_provider"] = provider_name
                    return result
                except json.JSONDecodeError:
                    return {"content": sanitized, "_provider": provider_name}
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"生成章节第 {idx + 1} 个版本时失败: {str(exc)[:200]}",
                ) from exc

        # 读取写作模型配置
        writing_models: List[str] = []
        model_revision_temps: dict[str, float] = {}  # 每个模型的修订温度
        record = await config_repo.get_by_key("writer.models")
        if record and record.value:
            try:
                models = json.loads(record.value)
                if isinstance(models, list) and models:
                    for m in models:
                        if isinstance(m, str):
                            writing_models.append(m)
                            model_revision_temps[m] = 0.3  # 默认值
                        elif isinstance(m, dict) and "name" in m:
                            name = m["name"]
                            writing_models.append(name)
                            # 读取修订温度，默认0.3
                            rev_temp = m.get("revision_temperature", 0.3)
                            try:
                                model_revision_temps[name] = float(rev_temp)
                            except (TypeError, ValueError):
                                model_revision_temps[name] = 0.3
            except (json.JSONDecodeError, TypeError):
                writing_models = []

        if not writing_models:
            raise HTTPException(status_code=400, detail="请先在设置页面配置写作模型")

        if rewrite_provider:
            result = await _generate_single_version(rewrite_target_index or 0, rewrite_provider)
            contents: List[str] = []
            metadata: List[dict] = []
            generated_contents: dict[str, str] = {}

            for idx, version in enumerate(existing_versions):
                if idx == rewrite_target_index:
                    variant = result
                    if isinstance(variant, dict):
                        if "content" in variant and isinstance(variant["content"], str):
                            content_text = variant["content"]
                        elif "chapter_content" in variant:
                            content_text = str(variant["chapter_content"])
                        else:
                            content_text = json.dumps(variant, ensure_ascii=False)
                        metadata.append(variant)
                    else:
                        content_text = str(variant)
                        metadata.append({"raw": variant, "_provider": rewrite_provider})
                    contents.append(content_text)
                    generated_contents[rewrite_provider] = content_text
                else:
                    contents.append(version.content or "")
                    extra = {"_provider": version.provider}
                    existing_meta = version.metadata_ if isinstance(version.metadata_, dict) else None
                    if existing_meta and existing_meta.get("_model"):
                        extra["_model"] = existing_meta.get("_model")
                    metadata.append(extra)

            await self.novel_service.replace_chapter_versions(chapter, contents, metadata)
            return generated_contents

        # 并行生成
        tasks = [_generate_single_version(idx, writing_models[idx]) for idx in range(len(writing_models))]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        raw_versions = [result for result in results if not isinstance(result, Exception)]
        if not raw_versions:
            raise HTTPException(status_code=500, detail="所有版本生成均失败，请检查模型配置")

        # 处理结果
        contents: List[str] = []
        metadata: List[dict] = []
        generated_contents: dict[str, str] = {}  # 记录各模型生成的内容

        for idx, variant in enumerate(raw_versions):
            provider_name = writing_models[idx] if idx < len(writing_models) else f"model_{idx}"
            content_text = ""

            if isinstance(variant, dict):
                if "content" in variant and isinstance(variant["content"], str):
                    content_text = variant["content"]
                elif "chapter_content" in variant:
                    content_text = str(variant["chapter_content"])
                else:
                    content_text = json.dumps(variant, ensure_ascii=False)
                metadata.append(variant)
            else:
                content_text = str(variant)
                metadata.append({"raw": variant})

            contents.append(content_text)
            generated_contents[provider_name] = content_text

        await self.novel_service.replace_chapter_versions(chapter, contents, metadata)

        return generated_contents

    async def _evaluate_chapter_internal(
        self,
        *,
        project_id: str,
        user_id: int,
        chapter_number: int,
    ) -> ChapterReviewResult:
        """
        内部评审方法

        使用改进版评估提示词，返回结构化的评审结果
        """
        project = await self.novel_service.ensure_project_owner(project_id, user_id)
        chapter = next((ch for ch in project.chapters if ch.chapter_number == chapter_number), None)

        if not chapter:
            raise HTTPException(status_code=404, detail="章节不存在")
        if not chapter.versions:
            raise HTTPException(status_code=400, detail="无可评估的章节版本")

        # 加载评估提示词
        evaluator_prompt = await self._load_evaluation_prompt()

        # 构建评估 payload
        project_schema = await self.novel_service._serialize_project(project)
        blueprint_dict = project_schema.blueprint.model_dump()
        outlines_map = {item.chapter_number: item for item in project.outlines}

        # 收集前序章节摘要（不包含完整内容以减少 payload）
        completed_chapters = []
        for existing in project.chapters:
            if existing.chapter_number >= chapter_number:
                continue
            if existing.selected_version is None or not existing.selected_version.content:
                continue
            if not existing.real_summary:
                summary_chunks = []
                async for chunk in self.llm_service.stream_node(
                    "outline",
                    existing.selected_version.content,
                    user_id=user_id,
                ):
                    if chunk.get("content"):
                        summary_chunks.append(chunk["content"])
                existing.real_summary = remove_think_tags("".join(summary_chunks))
                await self.session.commit()

            completed_chapters.append(
                {
                    "chapter_number": existing.chapter_number,
                    "title": outlines_map.get(existing.chapter_number).title
                    if outlines_map.get(existing.chapter_number)
                    else f"第{existing.chapter_number}章",
                    "summary": existing.real_summary or "",
                }
            )

        # 待评估版本
        versions_to_evaluate = [
            {"version_index": idx + 1, "content": version.content}
            for idx, version in enumerate(sorted(chapter.versions, key=lambda item: item.created_at))
        ]

        evaluator_payload = {
            "novel_blueprint": blueprint_dict,
            "completed_chapters": completed_chapters,
            "content_to_evaluate": {
                "chapter_number": chapter.chapter_number,
                "versions": versions_to_evaluate,
            },
        }

        # 调用评估（使用流式调用避免服务器端超时）
        evaluation_chunks = []
        async for chunk in self.llm_service.stream_node(
            "concept",
            [
                {"role": "system", "content": evaluator_prompt},
                {"role": "user", "content": json.dumps(evaluator_payload, ensure_ascii=False)},
            ],
            user_id=user_id,
        ):
            if chunk.get("content"):
                evaluation_chunks.append(chunk["content"])
        evaluation_raw = "".join(evaluation_chunks)

        # 解析结果
        evaluation_clean = sanitize_json_like_text(unwrap_markdown_json(remove_think_tags(evaluation_raw)))
        try:
            evaluation_data = json.loads(evaluation_clean)
            review = ChapterReviewResult.model_validate(evaluation_data)
        except Exception as exc:
            logger.error("评估结果解析失败: %s, 原始内容: %s", exc, evaluation_clean[:500])
            raise HTTPException(status_code=500, detail=f"评估结果解析失败: {str(exc)[:200]}") from exc

        # 保存评估记录
        await self.novel_service.add_chapter_evaluation(chapter, None, evaluation_clean)

        return review

    async def _load_evaluation_prompt(self) -> str:
        """加载评估提示词"""
        # 优先从数据库加载
        prompt = await self.prompt_service.get_prompt("evaluation_detailed")
        if prompt:
            return prompt

        # 降级从文件加载
        if _EVALUATION_PROMPT_PATH.exists():
            return _EVALUATION_PROMPT_PATH.read_text(encoding="utf-8")

        raise HTTPException(status_code=500, detail="缺少评审提示词 evaluation_detailed")

    def _format_avoid_issues(self, issues: List[DetailedWeakness]) -> str:
        """格式化需要避免的问题列表"""
        if not issues:
            return "无"

        lines = [
            f"{idx}. 【{item.location}】{item.issue}\n   改进方向：{item.suggestion}"
            for idx, item in enumerate(issues, start=1)
        ]
        return "\n".join(lines)

    def _deduplicate_weaknesses(self, items: List[DetailedWeakness]) -> List[DetailedWeakness]:
        """去重缺点列表"""
        seen = set()
        result: List[DetailedWeakness] = []

        for item in items:
            key = (item.location or "", item.issue or "", item.suggestion or "")
            key = tuple(part.strip().lower() for part in key)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)

        return result
