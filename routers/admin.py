from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models import User
from schemas.key_schemas import (
    FakeKeyCreate,
    FakeKeyOut,
    FakeKeyUpdate,
    MappingCreate,
    MappingOut,
    RealKeyCreate,
    RealKeyOut,
    RealKeyUpdate,
)
from schemas.stats_schemas import DashboardStats, DailyStatsOut, RequestLogOut
from schemas.user_schemas import TokenOut, UserCreate, UserLogin, UserOut, UserUpdate
from services import key_service, stats_service
from services.user_service import (
    authenticate,
    check_super_admin_exists,
    create_admin,
    create_super_admin,
    delete_user,
    get_user_by_id,
    list_users,
    update_user,
)
from utils.auth import create_access_token, require_admin, require_super_admin
from utils.db import get_db

router = APIRouter(prefix="/admin/api")


# ---------- Auth (no auth required) ----------

@router.get("/init-status")
async def init_status(db: AsyncSession = Depends(get_db)):
    return {"need_init": not await check_super_admin_exists(db)}


@router.post("/init", response_model=UserOut)
async def init_super_admin(data: UserCreate, db: AsyncSession = Depends(get_db)):
    if await check_super_admin_exists(db):
        raise HTTPException(status_code=400, detail="Super admin already exists")
    try:
        return await create_super_admin(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenOut)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(require_admin)):
    return user


# ---------- Users (super admin only) ----------

@router.get("/users", response_model=List[UserOut])
async def get_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    return await list_users(db)


@router.post("/users", response_model=UserOut)
async def post_admin(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    try:
        return await create_admin(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/users/{user_id}", response_model=UserOut)
async def put_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # 普通管理员只能修改自己
    if current_user.role != "super_admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    try:
        return await update_user(db, user, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{user_id}")
async def remove_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        await delete_user(db, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


# ---------- FakeKey ----------

@router.get("/fake-keys", response_model=List[FakeKeyOut])
async def list_fake_keys(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    return await key_service.list_fake_keys(db)


@router.post("/fake-keys", response_model=FakeKeyOut)
async def create_fake_key(data: FakeKeyCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    return await key_service.create_fake_key(db, data)


@router.put("/fake-keys/{key_id}", response_model=FakeKeyOut)
async def update_fake_key(key_id: int, data: FakeKeyUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    fk = await key_service.get_fake_key_by_id(db, key_id)
    if not fk:
        raise HTTPException(status_code=404, detail="Fake key not found")
    return await key_service.update_fake_key(db, fk, data)


@router.delete("/fake-keys/{key_id}")
async def delete_fake_key(key_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    fk = await key_service.get_fake_key_by_id(db, key_id)
    if not fk:
        raise HTTPException(status_code=404, detail="Fake key not found")
    await key_service.delete_fake_key(db, fk)
    return {"ok": True}


# ---------- RealKey ----------

@router.get("/real-keys", response_model=List[RealKeyOut])
async def list_real_keys(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    return await key_service.list_real_keys(db)


@router.post("/real-keys", response_model=RealKeyOut)
async def create_real_key(data: RealKeyCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    return await key_service.create_real_key(db, data)


@router.put("/real-keys/{key_id}", response_model=RealKeyOut)
async def update_real_key(key_id: int, data: RealKeyUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    rk = await key_service.get_real_key_by_id(db, key_id)
    if not rk:
        raise HTTPException(status_code=404, detail="Real key not found")
    return await key_service.update_real_key(db, rk, data)


@router.delete("/real-keys/{key_id}")
async def delete_real_key(key_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    rk = await key_service.get_real_key_by_id(db, key_id)
    if not rk:
        raise HTTPException(status_code=404, detail="Real key not found")
    await key_service.delete_real_key(db, rk)
    return {"ok": True}


# ---------- Mapping ----------

@router.get("/mappings", response_model=List[MappingOut])
async def list_mappings(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    return await key_service.list_mappings(db)


@router.post("/mappings", response_model=MappingOut)
async def create_mapping(data: MappingCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    try:
        return await key_service.create_mapping(db, data)
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="Mapping already exists")
        raise


@router.delete("/mappings/{mapping_id}")
async def delete_mapping(mapping_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    m = await key_service.get_mapping_by_id(db, mapping_id)
    if not m:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await key_service.delete_mapping(db, m)
    return {"ok": True}


# ---------- Stats ----------

@router.get("/stats/dashboard")
async def dashboard_stats(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> DashboardStats:
    return await stats_service.get_dashboard_stats(db)


@router.get("/stats/by-key")
async def stats_by_key(
    fake_key_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await stats_service.get_stats_by_key(db, fake_key_id, start_date, end_date)


@router.get("/logs")
async def list_logs(
    fake_key_id: Optional[int] = None,
    provider: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    logs, total = await stats_service.get_logs(db, fake_key_id, provider, start_date, end_date, limit, offset)
    return {
        "items": logs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
