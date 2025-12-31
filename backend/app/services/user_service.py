from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import hash_password
from ..models import User
from ..repositories.user_repository import UserRepository
from ..schemas.user import UserCreate, UserInDB


class UserService:
    """用户领域服务，负责注册、查询与配额统计。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)

    async def create_user(self, payload: UserCreate, *, external_id: str | None = None) -> UserInDB:
        hashed_password = hash_password(payload.password)
        user = User(
            username=payload.username,
            email=payload.email,
            hashed_password=hashed_password,
            external_id=external_id,
        )

        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ValueError("用户名或邮箱已存在") from exc

        return UserInDB.model_validate(user)

    async def get_by_username(self, username: str) -> Optional[UserInDB]:
        user = await self.repo.get_by_username(username)
        return UserInDB.model_validate(user) if user else None

    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        user = await self.repo.get_by_email(email)
        return UserInDB.model_validate(user) if user else None

    async def get_by_external_id(self, external_id: str) -> Optional[UserInDB]:
        user = await self.repo.get_by_external_id(external_id)
        return UserInDB.model_validate(user) if user else None

    async def get_user(self, user_id: int) -> Optional[UserInDB]:
        user = await self.repo.get(id=user_id)
        return UserInDB.model_validate(user) if user else None

    async def list_users(self) -> list[UserInDB]:
        users = await self.repo.list_all()
        return [UserInDB.model_validate(item) for item in users]

    async def increment_daily_request(self, user_id: int) -> None:
        await self.repo.increment_daily_request(user_id)
        await self.session.commit()

    async def get_daily_request(self, user_id: int) -> int:
        return await self.repo.get_daily_request(user_id)
