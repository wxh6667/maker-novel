from typing import Iterable, Optional

from sqlalchemy import select

from .base import BaseRepository
from ..models import SystemConfig


class SystemConfigRepository(BaseRepository[SystemConfig]):
    model = SystemConfig

    async def get_by_key(self, key: str) -> Optional[SystemConfig]:
        result = await self.session.execute(select(SystemConfig).where(SystemConfig.key == key))
        return result.scalars().first()

    async def list_all(self) -> Iterable[SystemConfig]:
        result = await self.session.execute(select(SystemConfig).order_by(SystemConfig.key))
        return result.scalars().all()

    async def upsert(self, key: str, value: str, description: Optional[str] = None) -> SystemConfig:
        """插入或更新配置项。"""
        record = await self.get_by_key(key)
        if record:
            record.value = value
            if description is not None:
                record.description = description
            await self.session.flush()
            return record
        else:
            new_record = SystemConfig(key=key, value=value, description=description)
            self.session.add(new_record)
            await self.session.flush()
            return new_record
