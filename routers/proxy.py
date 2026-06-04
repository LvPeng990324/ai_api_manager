from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from services.key_service import get_fake_key_by_key, get_real_keys_for_fake
from services.proxy_service import KNOWN_PROVIDERS, proxy_request
from utils.db import AsyncSessionLocal

router = APIRouter()


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    if len(parts) == 1:
        # 兼容直接传密钥（不带 Bearer 前缀）
        return parts[0]
    raise HTTPException(status_code=401, detail="Invalid Authorization header")


async def _infer_provider(db: AsyncSession, fake_key_id: int) -> str:
    """从假密钥绑定的真密钥中推断出默认厂商（取优先级最高的第一个）"""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from models import KeyMapping
    result = await db.execute(
        select(KeyMapping)
        .options(selectinload(KeyMapping.real_key))
        .where(KeyMapping.fake_key_id == fake_key_id)
        .order_by(KeyMapping.priority, KeyMapping.id)
    )
    mappings = result.scalars().all()
    for m in mappings:
        if m.real_key and m.real_key.enabled:
            return m.real_key.provider
    raise HTTPException(status_code=400, detail="No real key mapped for this fake key")


@router.api_route("/v1/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(
    full_path: str,
    request: Request,
    authorization: str | None = Header(None),
):
    """
    智能路由：
    - /v1/deepseek/chat/completions  → provider=deepseek, path=chat/completions
    - /v1/chat/completions           → 从假密钥推断 provider, path=chat/completions
    """
    fake_key_str = extract_bearer_token(authorization)

    async with AsyncSessionLocal() as db:
        fake_key = await get_fake_key_by_key(db, fake_key_str)
        if not fake_key or not fake_key.enabled:
            raise HTTPException(status_code=401, detail="Invalid or disabled fake key")

        # 解析 provider 和 path
        parts = full_path.split("/", 1)
        first_segment = parts[0]
        if first_segment in KNOWN_PROVIDERS:
            provider = first_segment
            path = parts[1] if len(parts) > 1 else ""
        else:
            # 路径第一段不是已知厂商，从假密钥推断
            provider = await _infer_provider(db, fake_key.id)
            path = full_path

        real_keys = await get_real_keys_for_fake(db, fake_key.id, provider)
        if not real_keys:
            raise HTTPException(status_code=400, detail=f"No real key mapped for provider: {provider}")

        # 取第一个可用的真密钥（已按优先级+随机排序）
        real_key = real_keys[0]

    return await proxy_request(
        provider, path, request, real_key, fake_key.id
    )
