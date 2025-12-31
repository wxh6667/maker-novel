"""重置管理员密码脚本"""
import asyncio
from sqlalchemy import select, update
from app.db.session import AsyncSessionLocal
from app.models import User
from app.core.security import hash_password
from app.core.config import settings


async def reset_admin():
    new_password = settings.admin_default_password
    async with AsyncSessionLocal() as session:
        # 查找管理员用户
        result = await session.execute(select(User).where(User.is_admin.is_(True)))
        admin = result.scalars().first()

        if admin:
            # 重置密码
            admin.hashed_password = hash_password(new_password)
            await session.commit()
            print(f"管理员密码已重置")
            print(f"用户名: {admin.username}")
            print(f"密码: {new_password}")
        else:
            # 创建新管理员
            new_admin = User(
                username=settings.admin_default_username,
                email=settings.admin_default_email,
                hashed_password=hash_password(settings.admin_default_password),
                is_admin=True,
            )
            session.add(new_admin)
            await session.commit()
            print(f"管理员账号已创建")
            print(f"用户名: {settings.admin_default_username}")
            print(f"密码: {settings.admin_default_password}")


if __name__ == "__main__":
    asyncio.run(reset_admin())
