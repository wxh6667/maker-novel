"""
评审打分重写流程的 Schema 定义
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DetailedWeakness(BaseModel):
    """结构化缺点 - 具体、可操作"""

    location: str = Field(..., description="问题位置，如'第2段'、'开头对话'")
    issue: str = Field(..., description="问题描述")
    suggestion: str = Field(..., description="改进建议")


class VersionReview(BaseModel):
    """单版本评审结果"""

    version_index: int
    score: int = Field(..., ge=0, le=100, description="评分 0-100")
    pros: List[str] = Field(default_factory=list)
    cons: List[DetailedWeakness] = Field(default_factory=list)
    overall_review: str = ""


class ChapterReviewResult(BaseModel):
    """章节评审结果"""

    best_choice: int
    reason_for_choice: str
    versions: List[VersionReview]


class ReviewStatus(str, Enum):
    """评审状态"""

    PASSED = "passed"  # 分数达标
    NEEDS_REWRITE = "needs_rewrite"  # 需要重写
    MAX_ATTEMPTS = "max_attempts"  # 达到最大尝试次数


class ReviewRewriteState(BaseModel):
    """评审-重写流程状态"""

    # 控制参数
    attempt: int = 0
    max_attempts: int = 3
    score_threshold: int = 70

    # 当前状态
    current_score: int = 0
    status: ReviewStatus = ReviewStatus.NEEDS_REWRITE

    # 累积的缺点（用于下次生成时避免）
    accumulated_weaknesses: List[DetailedWeakness] = Field(default_factory=list)

    # 历史记录
    review_history: List[ChapterReviewResult] = Field(default_factory=list)


class GenerateWithReviewRequest(BaseModel):
    """带评审的生成请求"""

    chapter_number: int
    writing_notes: Optional[str] = Field(default=None, description="章节额外写作指令")
    rewrite_provider: Optional[str] = Field(default=None, description="仅重写指定模型/供应商")

    # 评审配置
    score_threshold: int = Field(default=70, ge=0, le=100, description="分数阈值")
    max_attempts: int = Field(default=3, ge=1, le=5, description="最大尝试次数")
    auto_select_best: bool = Field(default=True, description="自动选择最佳版本")


class GenerateWithReviewResponse(BaseModel):
    """带评审的生成响应"""

    success: bool
    final_score: int
    attempts_used: int
    status: ReviewStatus
    best_version_index: int
    review_history: List[ChapterReviewResult]
    accumulated_feedback: List[DetailedWeakness]
