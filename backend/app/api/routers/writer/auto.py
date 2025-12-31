import json
import logging
from typing import AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.config import settings
from ....core.dependencies import get_current_user
from ....db.session import get_session
from ....schemas.novel import AutoCreateRequest, EvaluateChapterRequest, GenerateChapterRequest, ChapterGenerationStatus
from ....schemas.user import UserInDB
from ....services.chapter_ingest_service import ChapterIngestionService
from ....services.llm_service import LLMService
from ....services.novel_service import NovelService
from ....services.vector_store_service import VectorStoreService
from ....utils.json_utils import remove_think_tags, unwrap_markdown_json, sanitize_json_like_text
from ....repositories.system_config_repository import SystemConfigRepository

from .common import _creation_sessions, acquire_creation_lock, release_creation_lock
from .chapter import generate_chapter
from .review import evaluate_chapter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/novels/{project_id}/chapters/auto-create/stop")
async def stop_auto_create(
    project_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    停止正在进行的连续创作。
    """
    session_state = _creation_sessions.get(project_id)
    if session_state and session_state.get("mode") == "auto":
        session_state["cancel_requested"] = True
        logger.info("用户 %s 请求停止项目 %s 的连续创作", current_user.id, project_id)
        return {"status": "stop_requested", "message": "已发送停止请求"}
    return {"status": "not_running", "message": "该项目没有正在进行的连续创作"}


@router.post("/novels/{project_id}/chapters/auto-create")
async def auto_create_chapters(
    project_id: str,
    request: AutoCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    """
    连续创作模式：自动生成、评估、选择并入库多个章节。
    返回 SSE 流式事件，实时报告进度。
    """
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    outlines = sorted(project.outlines, key=lambda item: item.chapter_number)
    if not outlines:
        raise HTTPException(status_code=400, detail="尚未生成章节大纲，无法自动创作")

    outline_numbers = [item.chapter_number for item in outlines]
    if request.start_chapter is None:
        start_chapter = None
        for number in outline_numbers:
            chapter = next((ch for ch in project.chapters if ch.chapter_number == number), None)
            if not chapter or chapter.selected_version is None or not chapter.selected_version.content:
                start_chapter = number
                break
        if start_chapter is None:
            raise HTTPException(status_code=400, detail="当前没有可自动创作的章节")
    else:
        start_chapter = request.start_chapter

    end_chapter = request.end_chapter if request.end_chapter is not None else outline_numbers[-1]
    if start_chapter > end_chapter:
        raise HTTPException(status_code=400, detail="章节范围不合法")
    if start_chapter < outline_numbers[0] or end_chapter > outline_numbers[-1]:
        raise HTTPException(status_code=400, detail="章节范围超出大纲范围")

    # 读取分数阈值配置
    config_repo = SystemConfigRepository(session)
    early_threshold_record = await config_repo.get_by_key("writer.score_threshold_early")
    normal_threshold_record = await config_repo.get_by_key("writer.score_threshold_normal")
    max_attempts_record = await config_repo.get_by_key("writer.max_rewrite_attempts")

    score_threshold_early = int(early_threshold_record.value) if early_threshold_record and early_threshold_record.value else 95
    score_threshold_normal = int(normal_threshold_record.value) if normal_threshold_record and normal_threshold_record.value else 90
    max_rewrite_attempts = int(max_attempts_record.value) if max_attempts_record and max_attempts_record.value else 3

    def _sse(event: str, data: Dict) -> str:
        payload = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {payload}\n\n"

    async def _stream() -> AsyncGenerator[str, None]:
        chapters_created = 0
        total_chapters = end_chapter - start_chapter + 1
        try:
            yield _sse(
                "start",
                {
                    "start_chapter": start_chapter,
                    "end_chapter": end_chapter,
                    "total_chapters": total_chapters,
                },
            )

            for chapter_number in range(start_chapter, end_chapter + 1):
                # 检查停止信号
                if _creation_sessions.get(project_id, {}).get("cancel_requested"):
                    logger.info("项目 %s 连续创作在第 %s 章被用户停止", project_id, chapter_number)
                    yield _sse(
                        "stopped",
                        {
                            "chapter": chapter_number,
                            "chapters_created": chapters_created,
                            "message": f"已在第{chapter_number}章停止",
                        },
                    )
                    return

                # 计算当前章节的分数阈值：前三章使用 early 阈值，后续使用 normal 阈值
                score_threshold = score_threshold_early if chapter_number <= 3 else score_threshold_normal

                try:
                    best_choice = None
                    best_index = -1
                    score = None
                    selected = None
                    evaluation_data = None
                    last_round_feedback = None  # 用于存储上一轮评审反馈

                    for attempt in range(1, max_rewrite_attempts + 1):
                        # 检查停止信号
                        if _creation_sessions.get(project_id, {}).get("cancel_requested"):
                            logger.info("项目 %s 连续创作在第 %s 章重写时被用户停止", project_id, chapter_number)
                            yield _sse(
                                "stopped",
                                {
                                    "chapter": chapter_number,
                                    "chapters_created": chapters_created,
                                    "message": f"已在第{chapter_number}章停止",
                                },
                            )
                            return

                        yield _sse(
                            "progress",
                            {
                                "chapter": chapter_number,
                                "stage": "generating",
                                "message": f"生成第{chapter_number}章（第{attempt}/{max_rewrite_attempts}次）",
                            },
                        )

                        # 注入上一轮评审反馈到写作指令
                        original_writing_notes = request.writing_notes or ""
                        effective_writing_notes = original_writing_notes
                        if last_round_feedback:
                            pros_lines = "\n".join(f"✓ {p}" for p in last_round_feedback.get("pros", []) if p)
                            cons_lines = "\n".join(f"- {c}" for c in last_round_feedback.get("cons", []) if c)
                            effective_writing_notes = "\n".join(
                                [
                                    "【修订任务】请基于上一版本进行改进：",
                                    "[需要保持的优点]",
                                    pros_lines or "无",
                                    "[需要修复的问题]",
                                    cons_lines or "无",
                                    "",
                                    "[原始写作指令]",
                                    original_writing_notes or "无",
                                ]
                            ).strip()

                        await generate_chapter(
                            project_id,
                            GenerateChapterRequest(
                                chapter_number=chapter_number,
                                writing_notes=effective_writing_notes or None,
                            ),
                            session=session,
                            current_user=current_user,
                            _internal_call=True,  # 内部调用，跳过锁
                        )

                        yield _sse(
                            "progress",
                            {
                                "chapter": chapter_number,
                                "stage": "evaluating",
                                "message": f"评估第{chapter_number}章版本（第{attempt}/{max_rewrite_attempts}次）",
                            },
                        )
                        # 清除 session 缓存，确保 evaluate_chapter 能看到新创建的章节
                        session.expire_all()
                        await evaluate_chapter(
                            project_id,
                            EvaluateChapterRequest(chapter_number=chapter_number),
                            session=session,
                            current_user=current_user,
                        )

                        project_inner = await novel_service.ensure_project_owner(project_id, current_user.id)
                        chapter = next((ch for ch in project_inner.chapters if ch.chapter_number == chapter_number), None)
                        if not chapter or not chapter.evaluations:
                            raise HTTPException(status_code=500, detail="评估结果缺失")
                        latest_evaluation = sorted(chapter.evaluations, key=lambda item: item.created_at)[-1]
                        evaluation_text = latest_evaluation.feedback or latest_evaluation.decision
                        if not evaluation_text:
                            raise HTTPException(status_code=500, detail="评估结果为空")

                        evaluation_clean = unwrap_markdown_json(remove_think_tags(evaluation_text))
                        evaluation_clean = sanitize_json_like_text(evaluation_clean)
                        try:
                            evaluation_data = json.loads(evaluation_clean)
                        except json.JSONDecodeError as exc:
                            raise HTTPException(status_code=500, detail=f"评估结果解析失败: {str(exc)}") from exc

                        try:
                            best_choice = int(evaluation_data.get("best_choice"))
                        except (TypeError, ValueError) as exc:
                            raise HTTPException(status_code=500, detail="评估结果缺少有效的 best_choice") from exc

                        best_index = best_choice - 1
                        if best_index < 0:
                            raise HTTPException(status_code=500, detail="评估结果 best_choice 不合法")

                        # 获取最佳版本的分数和优缺点
                        score = None
                        best_pros = []
                        best_cons = []
                        versions_data = evaluation_data.get("versions")
                        if isinstance(versions_data, list):
                            for item in versions_data:
                                if not isinstance(item, dict):
                                    continue
                                try:
                                    version_index = int(item.get("version_index"))
                                except (TypeError, ValueError):
                                    continue
                                if version_index == best_choice:
                                    score = item.get("score")
                                    best_pros = item.get("pros") or []
                                    best_cons = item.get("cons") or []
                                    break
                        # 兼容旧格式 evaluation.versionX
                        elif isinstance(evaluation_data.get("evaluation"), dict):
                            version_key = f"version{best_choice}"
                            eval_item = evaluation_data["evaluation"].get(version_key)
                            if isinstance(eval_item, dict):
                                score = eval_item.get("score")
                                best_pros = eval_item.get("pros") or []
                                best_cons = eval_item.get("cons") or []

                        # 格式化缺点（兼容新旧格式）
                        formatted_cons = []
                        for con in best_cons:
                            if isinstance(con, dict):
                                parts = []
                                if con.get("location"):
                                    parts.append(f"位置：{con['location']}")
                                if con.get("issue"):
                                    parts.append(f"问题：{con['issue']}")
                                if con.get("suggestion"):
                                    parts.append(f"建议：{con['suggestion']}")
                                if parts:
                                    formatted_cons.append(" | ".join(parts))
                            elif con:
                                formatted_cons.append(str(con))

                        # 存储本轮反馈，供下一轮使用
                        last_round_feedback = {
                            "pros": [str(p) for p in best_pros if p],
                            "cons": formatted_cons,
                        }
                        try:
                            score = int(score) if score is not None else 0
                        except (TypeError, ValueError):
                            score = 0

                        logger.info(
                            "项目 %s 第 %s 章：第 %s 次尝试，最高分 %s（阈值 %s）",
                            project_id,
                            chapter_number,
                            attempt,
                            score,
                            score_threshold,
                        )

                        # 检查分数是否达标
                        if score >= score_threshold:
                            logger.info(
                                "项目 %s 第 %s 章：分数达标，选择版本 %s",
                                project_id,
                                chapter_number,
                                best_choice,
                            )
                            break

                        # 分数不达标，检查是否还有重写机会
                        if attempt < max_rewrite_attempts:
                            yield _sse(
                                "progress",
                                {
                                    "chapter": chapter_number,
                                    "stage": "rewriting",
                                    "message": f"第{chapter_number}章分数 {score} 未达标（阈值 {score_threshold}），准备重写",
                                },
                            )
                        else:
                            # 已达最大重写次数，分数仍不达标
                            logger.warning(
                                "项目 %s 第 %s 章：%s 次重写后分数仍为 %s，未达阈值 %s，停止连续创作",
                                project_id,
                                chapter_number,
                                max_rewrite_attempts,
                                score,
                                score_threshold,
                            )
                            yield _sse(
                                "chapter_error",
                                {
                                    "chapter": chapter_number,
                                    "message": f"第{chapter_number}章经过{max_rewrite_attempts}次重写，最高分{score}仍未达到阈值{score_threshold}",
                                },
                            )
                            yield _sse(
                                "complete",
                                {
                                    "chapters_created": chapters_created,
                                    "message": f"第{chapter_number}章质量未达标，已停止连续创作",
                                },
                            )
                            return

                    # 分数达标，选择最佳版本
                    yield _sse(
                        "progress",
                        {
                            "chapter": chapter_number,
                            "stage": "selecting",
                            "message": f"自动选择第{chapter_number}章最佳版本（分数: {score}）",
                        },
                    )
                    selected = await novel_service.select_chapter_version(chapter, best_index)

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

                    yield _sse(
                        "progress",
                        {
                            "chapter": chapter_number,
                            "stage": "ingesting",
                            "message": f"第{chapter_number}章向量入库",
                        },
                    )
                    vector_store: Optional[VectorStoreService]
                    if not settings.vector_store_enabled:
                        vector_store = None
                    else:
                        try:
                            vector_store = VectorStoreService()
                        except RuntimeError as exc:
                            logger.warning("向量库初始化失败，跳过章节向量同步: %s", exc)
                            vector_store = None

                    if vector_store and selected and selected.content:
                        ingestion_service = ChapterIngestionService(
                            llm_service=llm_service,
                            vector_store=vector_store,
                        )
                        outline = next(
                            (item for item in project_inner.outlines if item.chapter_number == chapter.chapter_number),
                            None,
                        )
                        chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
                        await ingestion_service.ingest_chapter(
                            project_id=project_id,
                            chapter_number=chapter.chapter_number,
                            title=chapter_title,
                            content=selected.content,
                            summary=chapter.real_summary,
                            user_id=current_user.id,
                        )

                    # 向量入库完成后，将章节状态更新为 SUCCESSFUL
                    chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
                    await session.commit()

                    word_count = len(selected.content or "") if selected else 0
                    # 构建章节更新数据，供前端增量更新 Store
                    chapter_update_data = {
                        "chapter_number": chapter_number,
                        "status": chapter.status,
                        "selected_version_index": best_choice - 1 if best_choice else None,
                        "real_summary": chapter.real_summary,
                    }
                    yield _sse(
                        "chapter_done",
                        {
                            "chapter": chapter_number,
                            "selected_version": best_choice,
                            "score": score,
                            "word_count": word_count,
                            "chapter_data": chapter_update_data,
                        },
                    )
                    chapters_created += 1
                except HTTPException as exc:
                    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
                    yield _sse(
                        "chapter_error",
                        {
                            "chapter": chapter_number,
                            "message": message,
                        },
                    )
                    if request.auto_stop_on_error:
                        yield _sse(
                            "complete",
                            {
                                "chapters_created": chapters_created,
                                "message": f"已在第{chapter_number}章停止",
                            },
                        )
                        return
                except Exception as exc:
                    logger.exception("自动创作第 %s 章失败: %s", chapter_number, exc)
                    yield _sse(
                        "chapter_error",
                        {
                            "chapter": chapter_number,
                            "message": f"第{chapter_number}章处理失败",
                        },
                    )
                    if request.auto_stop_on_error:
                        yield _sse(
                            "complete",
                            {
                                "chapters_created": chapters_created,
                                "message": f"已在第{chapter_number}章停止",
                            },
                        )
                        return

            yield _sse(
                "complete",
                {
                    "chapters_created": chapters_created,
                    "message": "自动创作完成",
                },
            )
        except Exception as exc:
            logger.exception("自动创作流程异常中断: %s", exc)
            yield _sse(
                "error",
                {
                    "message": "自动创作流程异常中断",
                },
            )
        finally:
            # 释放创作锁
            await release_creation_lock(project_id, "auto")
            logger.debug("项目 %s 连续创作会话已清理", project_id)

    # 获取创作锁（自动模式）
    await acquire_creation_lock(project_id, "auto", current_user.id)
    return StreamingResponse(_stream(), media_type="text/event-stream")
