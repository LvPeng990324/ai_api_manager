import random
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import FakeKey, KeyMapping, RealKey
from schemas.key_schemas import FakeKeyCreate, FakeKeyUpdate, MappingCreate, RealKeyCreate, RealKeyUpdate
from utils.crypto import decrypt, encrypt


# ---------- FakeKey ----------

async def list_fake_keys(db: AsyncSession) -> List[FakeKey]:
    result = await db.execute(
        select(FakeKey).options(selectinload(FakeKey.mappings)).order_by(FakeKey.id.desc())
    )
    return result.scalars().all()


async def get_fake_key_by_id(db: AsyncSession, key_id: int) -> Optional[FakeKey]:
    result = await db.execute(select(FakeKey).where(FakeKey.id == key_id))
    return result.scalar_one_or_none()


async def get_fake_key_by_key(db: AsyncSession, key: str) -> Optional[FakeKey]:
    result = await db.execute(select(FakeKey).where(FakeKey.key == key))
    return result.scalar_one_or_none()


async def create_fake_key(db: AsyncSession, data: FakeKeyCreate) -> FakeKey:
    fk = FakeKey(name=data.name, enabled=data.enabled)
    db.add(fk)
    await db.commit()
    await db.refresh(fk)
    return fk


async def update_fake_key(db: AsyncSession, fk: FakeKey, data: FakeKeyUpdate) -> FakeKey:
    if data.name is not None:
        fk.name = data.name
    if data.enabled is not None:
        fk.enabled = data.enabled
    await db.commit()
    await db.refresh(fk)
    return fk


async def delete_fake_key(db: AsyncSession, fk: FakeKey) -> None:
    await db.delete(fk)
    await db.commit()


# ---------- RealKey ----------

async def list_real_keys(db: AsyncSession) -> List[RealKey]:
    result = await db.execute(
        select(RealKey).options(selectinload(RealKey.mappings)).order_by(RealKey.id.desc())
    )
    return result.scalars().all()


async def get_real_key_by_id(db: AsyncSession, key_id: int) -> Optional[RealKey]:
    result = await db.execute(select(RealKey).where(RealKey.id == key_id))
    return result.scalar_one_or_none()


def _normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


async def create_real_key(db: AsyncSession, data: RealKeyCreate) -> RealKey:
    rk = RealKey(
        provider=data.provider,
        base_url=_normalize_base_url(data.base_url),
        key=encrypt(data.key),
        name=data.name,
        enabled=data.enabled,
    )
    db.add(rk)
    await db.commit()
    await db.refresh(rk)
    return rk


async def update_real_key(db: AsyncSession, rk: RealKey, data: RealKeyUpdate) -> RealKey:
    if data.provider is not None:
        rk.provider = data.provider
    if data.base_url is not None:
        rk.base_url = _normalize_base_url(data.base_url)
    if data.key is not None:
        rk.key = encrypt(data.key)
    if data.name is not None:
        rk.name = data.name
    if data.enabled is not None:
        rk.enabled = data.enabled
    await db.commit()
    await db.refresh(rk)
    return rk


async def delete_real_key(db: AsyncSession, rk: RealKey) -> None:
    await db.delete(rk)
    await db.commit()


def get_real_key_decrypted(rk: RealKey) -> str:
    return decrypt(rk.key)


# ---------- Mapping ----------

async def list_mappings(db: AsyncSession) -> List[KeyMapping]:
    result = await db.execute(
        select(KeyMapping)
        .options(selectinload(KeyMapping.fake_key), selectinload(KeyMapping.real_key))
        .order_by(KeyMapping.priority, KeyMapping.id)
    )
    return result.scalars().all()


async def create_mapping(db: AsyncSession, data: MappingCreate) -> KeyMapping:
    m = KeyMapping(
        fake_key_id=data.fake_key_id,
        real_key_id=data.real_key_id,
        priority=data.priority,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    # 急加载关联对象
    result = await db.execute(
        select(KeyMapping)
        .options(selectinload(KeyMapping.fake_key), selectinload(KeyMapping.real_key))
        .where(KeyMapping.id == m.id)
    )
    return result.scalar_one()


async def delete_mapping(db: AsyncSession, m: KeyMapping) -> None:
    await db.delete(m)
    await db.commit()


async def get_mapping_by_id(db: AsyncSession, mapping_id: int) -> Optional[KeyMapping]:
    result = await db.execute(select(KeyMapping).where(KeyMapping.id == mapping_id))
    return result.scalar_one_or_none()


async def get_real_keys_for_fake(db: AsyncSession, fake_key_id: int) -> List[RealKey]:
    """获取某个假密钥映射的所有启用真密钥（按优先级排序，同优先级随机打乱）"""
    result = await db.execute(
        select(KeyMapping)
        .options(selectinload(KeyMapping.real_key))
        .where(KeyMapping.fake_key_id == fake_key_id)
        .order_by(KeyMapping.priority, KeyMapping.id)
    )
    mappings = result.scalars().all()

    # 按优先级分组，同优先级随机打乱
    priority_groups = {}
    for m in mappings:
        rk = m.real_key
        if rk and rk.enabled:
            priority_groups.setdefault(m.priority, []).append(rk)

    if not priority_groups:
        return []

    sorted_keys = []
    for p in sorted(priority_groups.keys()):
        group = priority_groups[p]
        random.shuffle(group)
        sorted_keys.extend(group)

    return sorted_keys
