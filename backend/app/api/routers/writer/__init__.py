from fastapi import APIRouter

from . import auto, chapter, outline, review

router = APIRouter(prefix="/api/writer", tags=["Writer"])
router.include_router(chapter.router)
router.include_router(outline.router)
router.include_router(review.router)
router.include_router(auto.router)
