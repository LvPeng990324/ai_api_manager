from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User
from schemas.user_schemas import UserCreate, UserUpdate
from utils.crypto import hash_password, verify_password


async def check_super_admin_exists(db: AsyncSession) -> bool:
    result = await db.execute(select(User).where(User.role == "super_admin").limit(1))
    return result.scalar_one_or_none() is not None


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_super_admin(db: AsyncSession, data: UserCreate) -> User:
    if await check_super_admin_exists(db):
        raise ValueError("Super admin already exists")
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role="super_admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_admin(db: AsyncSession, data: UserCreate) -> User:
    if await get_user_by_username(db, data.username):
        raise ValueError("Username already exists")
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    if data.username is not None:
        existing = await get_user_by_username(db, data.username)
        if existing and existing.id != user.id:
            raise ValueError("Username already exists")
        user.username = data.username
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user: User) -> None:
    if user.role == "super_admin":
        raise ValueError("Cannot delete super admin")
    await db.delete(user)
    await db.commit()


async def authenticate(db: AsyncSession, username: str, password: str) -> Optional[User]:
    user = await get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def list_users(db: AsyncSession) -> List[User]:
    result = await db.execute(select(User).order_by(User.id.desc()))
    return result.scalars().all()
