from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.usage_metric_repository import UsageMetricRepository


class UsageService:
    """通用计数服务，目前用于统计 API 请求次数等。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UsageMetricRepository(session)

    async def increment(self, key: str) -> None:
        counter = await self.repo.get_or_create(key)
        counter.value += 1
        await self.session.commit()

    async def get_value(self, key: str) -> int:
        counter = await self.repo.get_or_create(key)
        await self.session.commit()
        return counter.value
