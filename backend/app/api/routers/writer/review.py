import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ....core.dependencies import get_current_user
from ....db.session import get_session
from ....schemas.novel import (
    ChapterGenerationStatus,
    EvaluateChapterRequest,
    NovelProject as NovelProjectSchema,
)
from ....schemas.review import GenerateWithReviewRequest, GenerateWithReviewResponse
from ....schemas.user import UserInDB
from ....services.llm_service import LLMService
from ....services.novel_service import NovelService
from ....services.prompt_service import PromptService
from ....services.review_rewrite_service import ReviewRewriteService
from ....utils.json_utils import remove_think_tags, unwrap_markdown_json, sanitize_json_like_text

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法执行评估", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.versions:
        logger.warning("项目 %s 第 %s 章无可评估版本", project_id, request.chapter_number)
        raise HTTPException(status_code=400, detail="无可评估的章节版本")

    # 设置章节状态为评审中，确保前端轮询获取正确状态
    chapter.status = ChapterGenerationStatus.EVALUATING.value
    await session.commit()
    await session.refresh(chapter)

    try:
        evaluator_prompt = await prompt_service.get_prompt("evaluation")
        logger.debug("评审提示词 (前200字符): %s", evaluator_prompt[:200] if evaluator_prompt else "空")
        if not evaluator_prompt:
            logger.error("缺少评估提示词，项目 %s 第 %s 章评估失败", project_id, request.chapter_number)
            raise HTTPException(status_code=500, detail="缺少评估提示词，请联系管理员配置 'evaluation' 提示词")

        project_schema = await novel_service._serialize_project(project)
        blueprint_dict = project_schema.blueprint.model_dump()

        # 按创建时间排序版本
        versions_sorted = sorted(chapter.versions, key=lambda item: item.created_at)
        versions_to_evaluate = [
            {"version_id": idx + 1, "content": version.content}
            for idx, version in enumerate(versions_sorted)
        ]
        evaluator_payload = {
            "novel_blueprint": blueprint_dict,
            "content_to_evaluate": {
                "chapter_number": chapter.chapter_number,
                "versions": versions_to_evaluate,
            },
        }

        # 计算输入数据量
        payload_json = json.dumps(evaluator_payload, ensure_ascii=False)
        total_input_len = len(evaluator_prompt) + len(payload_json)
        logger.debug("评审输入总长度: %d 字符 (提示词: %d, 数据: %d, 版本数: %d)",
                     total_input_len, len(evaluator_prompt), len(payload_json), len(versions_to_evaluate))

        # 使用流式调用避免服务器端超时
        evaluation_chunks = []
        async for chunk in llm_service.stream_node(
            "evaluation",
            [
                {"role": "system", "content": evaluator_prompt},
                {"role": "user", "content": json.dumps(evaluator_payload, ensure_ascii=False)},
            ],
            user_id=current_user.id,
            response_format="json_object",
        ):
            if chunk.get("content"):
                evaluation_chunks.append(chunk["content"])
        evaluation_raw = "".join(evaluation_chunks)
        logger.debug("评审原始输出 (前500字符): %s", evaluation_raw[:500] if evaluation_raw else "空")
        evaluation_clean = sanitize_json_like_text(unwrap_markdown_json(remove_think_tags(evaluation_raw)))
        logger.debug("评审清洗后 (前500字符): %s", evaluation_clean[:500] if evaluation_clean else "空")

        # 解析评审结果，提取最佳版本和分数
        best_version = None
        best_score = None
        try:
            eval_data = json.loads(evaluation_clean)
            try:
                model_info = llm_service.get_node_model_info("evaluation")
                eval_data["_evaluation_model"] = model_info.get("model", "unknown")
                eval_data["_evaluation_provider"] = model_info.get("provider_name", "unknown")
            except Exception as e:
                logger.warning("获取评审模型信息失败: %s", e)

            best_choice = eval_data.get("best_choice", 1)
            if best_choice and 1 <= best_choice <= len(versions_sorted):
                best_version = versions_sorted[best_choice - 1]

            for v in eval_data.get("versions", []):
                if v.get("version_index") == best_choice:
                    best_score = v.get("score")
                    break

            evaluation_clean = json.dumps(eval_data, ensure_ascii=False)
        except json.JSONDecodeError:
            pass

        await novel_service.add_chapter_evaluation(chapter, best_version, evaluation_clean, score=best_score)
        logger.debug(
            "项目 %s 第 %s 章评估完成，绑定版本: %s，分数: %s",
            project_id, request.chapter_number,
            best_version.id if best_version else None, best_score,
        )

        return await novel_service.get_project_schema(project_id, current_user.id)
    except BaseException:
        # 捕获所有异常包括 CancelledError（继承自 BaseException）
        chapter.status = ChapterGenerationStatus.EVALUATION_FAILED.value
        await session.commit()
        raise


@router.post("/novels/{project_id}/chapters/evaluate/cancel", response_model=NovelProjectSchema)
async def cancel_evaluation(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """取消评审，将章节状态恢复到等待确认"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    
    # 允许取消的状态：评审中、评审失败
    allowed_statuses = [
        ChapterGenerationStatus.EVALUATING.value,
        ChapterGenerationStatus.EVALUATION_FAILED.value,
    ]
    
    if chapter.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"当前状态 {chapter.status} 不允许取消评审")
    
    chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
    await session.commit()
    logger.info("项目 %s 第 %s 章评审已取消", project_id, request.chapter_number)
    
    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post(
    "/novels/{project_id}/chapters/generate-with-review",
    response_model=GenerateWithReviewResponse,
)
async def generate_with_review(
    project_id: str,
    request: GenerateWithReviewRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> GenerateWithReviewResponse:
    """
    带评审的章节生成

    流程：
    1. 生成章节内容（多版本）
    2. AI 评审打分
    3. 分数不达标则重写（最多 max_attempts 次）
    4. 评审缺点作为下次生成的输入
    """
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 请求带评审生成项目 %s 第 %s 章，阈值 %s，最大尝试 %s",
        current_user.id,
        project_id,
        request.chapter_number,
        request.score_threshold,
        request.max_attempts,
    )
    if request.rewrite_provider:
        logger.info("用户 %s 指定单版本重写模型: %s", current_user.id, request.rewrite_provider)

    review_service = ReviewRewriteService(
        session=session,
        llm_service=llm_service,
        novel_service=novel_service,
        prompt_service=prompt_service,
    )

    return await review_service.generate_with_review(
        project_id=project_id,
        user_id=current_user.id,
        request=request,
    )
