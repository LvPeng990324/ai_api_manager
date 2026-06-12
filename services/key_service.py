import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import FakeKey, KeyMapping, RealKey
from schemas.key_schemas import FakeKeyCreate, FakeKeyUpdate, MappingCreate, RealKeyCreate, RealKeyUpdate
from utils.crypto import decrypt_cached, encrypt


_CACHE_TTL = timedelta(seconds=30)

_fake_key_cache: dict[str, tuple[Optional[FakeKey], datetime]] = {}
_fake_key_cache_lock = asyncio.Lock()

_mapping_cache: dict[int, tuple[List[RealKey], datetime]] = {}
_mapping_cache_lock = asyncio.Lock()


def _is_cache_valid(cached: tuple[object, datetime] | None) -> bool:
    return cached is not None and (datetime.utcnow() - cached[1]) < _CACHE_TTL


def _invalidate_fake_key_cache(key: str | None = None) -> None:
    if key is None:
        _fake_key_cache.clear()
    else:
        _fake_key_cache.pop(key, None)


def _invalidate_mapping_cache(fake_key_id: int | None = None) -> None:
    if fake_key_id is None:
        _mapping_cache.clear()
    else:
        _mapping_cache.pop(fake_key_id, None)


# ---------- FakeKey ----------

async def list_fake_keys(db: AsyncSession) -> List[FakeKey]:
    result = await db.execute(
        select(FakeKey).options(selectinload(FakeKey.mappings)).order_by(FakeKey.id.desc())
    )
    return result.scalars().all()


async def get_fake_key_by_id(db: AsyncSession, key_id: int) -> Optional[FakeKey]:
    result = await db.execute(select(FakeKey).where(FakeKey.id == key_id))
    return result.scalar_one_or_none()


async def _fetch_fake_key_by_key(db: AsyncSession, key: str) -> Optional[FakeKey]:
    result = await db.execute(select(FakeKey).where(FakeKey.key == key))
    return result.scalar_one_or_none()


async def get_fake_key_by_key(db: AsyncSession, key: str) -> Optional[FakeKey]:
    cached = _fake_key_cache.get(key)
    if _is_cache_valid(cached):
        return cached[0]

    async with _fake_key_cache_lock:
        cached = _fake_key_cache.get(key)
        if _is_cache_valid(cached):
            return cached[0]

        fk = await _fetch_fake_key_by_key(db, key)
        _fake_key_cache[key] = (fk, datetime.utcnow())
        return fk


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
    _invalidate_fake_key_cache(fk.key)
    return fk


async def delete_fake_key(db: AsyncSession, fk: FakeKey) -> None:
    await db.delete(fk)
    await db.commit()
    _invalidate_fake_key_cache(fk.key)
    _invalidate_mapping_cache(fk.id)


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
    _invalidate_mapping_cache()
    return rk


async def delete_real_key(db: AsyncSession, rk: RealKey) -> None:
    await db.delete(rk)
    await db.commit()
    _invalidate_mapping_cache()


def get_real_key_decrypted(rk: RealKey) -> str:
    return decrypt_cached(rk.key)


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
    _invalidate_mapping_cache(data.fake_key_id)
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
    _invalidate_mapping_cache(m.fake_key_id)


async def get_mapping_by_id(db: AsyncSession, mapping_id: int) -> Optional[KeyMapping]:
    result = await db.execute(select(KeyMapping).where(KeyMapping.id == mapping_id))
    return result.scalar_one_or_none()


async def _fetch_real_keys_for_fake(db: AsyncSession, fake_key_id: int) -> List[RealKey]:
    """获取某个假密钥映射的所有启用真密钥（按优先级排序，同优先级随机打乱）"""
    result = await db.execute(
        select(KeyMapping)
        .options(selectinload(KeyMapping.real_key))
        .where(KeyMapping.fake_key_id == fake_key_id)
        .order_by(KeyMapping.priority, KeyMapping.id)
    )
    mappings = result.scalars().all()

    priority_groups: dict[int, List[RealKey]] = {}
    for m in mappings:
        rk = m.real_key
        if rk and rk.enabled:
            priority_groups.setdefault(m.priority, []).append(rk)

    if not priority_groups:
        return []

    sorted_keys: List[RealKey] = []
    for p in sorted(priority_groups.keys()):
        group = priority_groups[p]
        sorted_keys.extend(random.sample(group, len(group)))

    return sorted_keys


async def get_real_keys_for_fake(db: AsyncSession, fake_key_id: int) -> List[RealKey]:
    cached = _mapping_cache.get(fake_key_id)
    if _is_cache_valid(cached):
        return cached[0]

    async with _mapping_cache_lock:
        cached = _mapping_cache.get(fake_key_id)
        if _is_cache_valid(cached):
            return cached[0]

        keys = await _fetch_real_keys_for_fake(db, fake_key_id)
        _mapping_cache[fake_key_id] = (keys, datetime.utcnow())
        return keys
