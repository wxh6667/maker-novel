from typing import Optional

from sqlalchemy import select

from .base import BaseRepository
from ..models import AdminSetting


class AdminSettingRepository(BaseRepository[AdminSetting]):
    model = AdminSetting

    async def get_value(self, key: str) -> Optional[str]:
        result = await self.session.execute(select(AdminSetting).where(AdminSetting.key == key))
        record = result.scalars().first()
        return record.value if record else None
