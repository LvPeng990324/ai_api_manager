from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from services.key_service import get_fake_key_by_key, get_real_keys_for_fake
from services.proxy_service import proxy_request
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


@router.api_route("/v1/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(
    full_path: str,
    request: Request,
    authorization: str | None = Header(None),
):
    """
    透明代理：
    - 下游使用 http://localhost:8000/v1 作为 base_url，路径保持 OpenAI 规范
    - 根据假密钥找到映射的真密钥，把请求转发到真密钥的 base_url + 原路径（去掉 /v1 重叠前缀）
    """
    fake_key_str = extract_bearer_token(authorization)

    async with AsyncSessionLocal() as db:
        fake_key = await get_fake_key_by_key(db, fake_key_str)
        if not fake_key or not fake_key.enabled:
            raise HTTPException(status_code=401, detail="Invalid or disabled fake key")

        real_keys = await get_real_keys_for_fake(db, fake_key.id)
        if not real_keys:
            raise HTTPException(status_code=400, detail="No real key mapped for this fake key")

        # 取第一个可用的真密钥（已按优先级+随机排序）
        real_key = real_keys[0]

    return await proxy_request(
        request, real_key, fake_key.id, full_path
    )
