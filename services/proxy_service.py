import asyncio
import json
import time
from typing import AsyncIterator, Optional

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from models import RealKey
from services.key_service import get_real_key_decrypted
from services.stats_service import record_request
from utils.db import AsyncSessionLocal

# 厂商配置
PROVIDERS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "custom": None,  # 通过配置传入
}

KNOWN_PROVIDERS = set(PROVIDERS.keys())


def get_provider_base_url(provider: str, custom_url: Optional[str] = None) -> str:
    if provider == "custom" and custom_url:
        return custom_url.rstrip("/")
    base = PROVIDERS.get(provider)
    if not base:
        raise ValueError(f"Unknown provider: {provider}")
    return base


async def extract_request_preview(body: bytes) -> str:
    """提取请求预览，最多100000字符"""
    try:
        data = json.loads(body)
        preview = json.dumps(data, ensure_ascii=False)
        return preview[:100000]
    except Exception:
        return body[:100000].decode("utf-8", errors="ignore")


def extract_model(body: bytes) -> str:
    try:
        data = json.loads(body)
        return data.get("model", "")
    except Exception:
        return ""


def parse_usage_from_response(data: dict) -> tuple[int, int]:
    """从响应中解析token使用量"""
    usage = data.get("usage", {})
    prompt = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
    completion = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
    return int(prompt), int(completion)


async def proxy_request(
    provider: str,
    path: str,
    request: Request,
    real_key: RealKey,
    fake_key_id: int,
) -> StreamingResponse | JSONResponse:
    """核心代理转发逻辑"""
    base_url = get_provider_base_url(provider)
    target_url = f"{base_url}/{path}"

    real_key_text = get_real_key_decrypted(real_key)

    # 读取请求体
    body = await request.body()
    request_preview = await extract_request_preview(body)
    model = extract_model(body)

    # 构建透传 headers
    headers = {}
    for key, value in request.headers.items():
        if key.lower() in ("host", "content-length", "authorization"):
            continue
        headers[key] = value
    headers["Authorization"] = f"Bearer {real_key_text}"

    method = request.method
    is_stream = False
    try:
        req_json = json.loads(body)
        is_stream = req_json.get("stream", False)
    except Exception:
        pass

    start_time = time.time()
    client = httpx.AsyncClient(timeout=300.0)

    try:
        if is_stream and method.upper() == "POST":
            return await _proxy_stream(
                client, target_url, method, headers, body,
                fake_key_id, real_key.id, provider, model,
                path, request_preview, start_time,
            )
        else:
            return await _proxy_non_stream(
                client, target_url, method, headers, body,
                fake_key_id, real_key.id, provider, model,
                path, request_preview, start_time,
            )
    except Exception:
        await client.aclose()
        raise


async def _proxy_non_stream(
    client: httpx.AsyncClient,
    target_url: str,
    method: str,
    headers: dict,
    body: bytes,
    fake_key_id: int,
    real_key_id: int,
    provider: str,
    model: str,
    endpoint: str,
    request_preview: str,
    start_time: float,
) -> JSONResponse:
    response = await client.request(method, target_url, headers=headers, content=body)
    resp_body = await response.aread()
    latency_ms = int((time.time() - start_time) * 1000)

    tokens_input = 0
    tokens_output = 0
    try:
        data = json.loads(resp_body)
        tokens_input, tokens_output = parse_usage_from_response(data)
    except Exception:
        pass

    # 只记录模型聊天请求
    if "chat/completions" in endpoint:
        async with AsyncSessionLocal() as log_db:
            await record_request(
                log_db, fake_key_id, real_key_id, provider, model, endpoint,
                response.status_code, latency_ms, tokens_input, tokens_output, request_preview,
            )

    await client.aclose()

    return JSONResponse(
        content=json.loads(resp_body) if resp_body else {},
        status_code=response.status_code,
        headers={k: v for k, v in response.headers.items() if k.lower() not in ("content-length", "transfer-encoding")},
    )


async def _proxy_stream(
    client: httpx.AsyncClient,
    target_url: str,
    method: str,
    headers: dict,
    body: bytes,
    fake_key_id: int,
    real_key_id: int,
    provider: str,
    model: str,
    endpoint: str,
    request_preview: str,
    start_time: float,
) -> StreamingResponse:
    req = client.build_request(method, target_url, headers=headers, content=body)
    response = await client.send(req)

    async def event_generator() -> AsyncIterator[bytes]:
        output_text = ""
        usage_found = False
        tokens_input = 0
        tokens_output = 0
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
                # 尝试从 chunk 中解析 usage
                if not usage_found:
                    try:
                        text = chunk.decode("utf-8")
                        for line in text.split("\n"):
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    continue
                                try:
                                    data = json.loads(data_str)
                                    u = data.get("usage")
                                    if u:
                                        tokens_input = u.get("prompt_tokens", 0) or u.get("input_tokens", 0)
                                        tokens_output = u.get("completion_tokens", 0) or u.get("output_tokens", 0)
                                        usage_found = True
                                    # 累加输出文本用于估算
                                    for choice in data.get("choices", []):
                                        delta = choice.get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            output_text += content
                                except Exception:
                                    pass
                    except Exception:
                        pass
        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            if not usage_found and output_text:
                # 粗略估算: 1 token ≈ 4 字符 (中文) 或 1 token ≈ 4 字符 (英文)
                # 简化处理：按字符数/4估算
                tokens_output = max(1, len(output_text) // 4)

            # 在独立 task 中写日志，避免在 anyio cancel scope / 已取消的上下文内执行 SQLAlchemy greenlet
            async def _do_record():
                if "chat/completions" not in endpoint:
                    return
                try:
                    async with AsyncSessionLocal() as log_db:
                        await record_request(
                            log_db, fake_key_id, real_key_id, provider, model, endpoint,
                            response.status_code, latency_ms, tokens_input, tokens_output, request_preview,
                        )
                except Exception:
                    pass

            try:
                asyncio.get_event_loop().create_task(_do_record())
            except Exception:
                pass

            try:
                await response.aclose()
            except BaseException:
                pass
            try:
                await client.aclose()
            except BaseException:
                pass

    return StreamingResponse(
        event_generator(),
        status_code=response.status_code,
        media_type="text/event-stream",
        headers={k: v for k, v in response.headers.items() if k.lower() not in ("content-length", "transfer-encoding")},
    )
