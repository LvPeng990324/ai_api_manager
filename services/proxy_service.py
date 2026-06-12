import json
import time
from typing import AsyncIterator, Optional

import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse

from models import RealKey
from services.key_service import get_real_key_decrypted
from services.stats_service import record_request
from utils.background import run_in_background
from utils.db import AsyncSessionLocal
from utils.http_client import get_http_client

_MAX_PREVIEW_LEN = 10000


def _build_target_url(real_key: RealKey, full_path: str) -> str:
    base_url = real_key.base_url.strip().rstrip("/")
    if not base_url:
        raise ValueError("Real key base_url is empty")
    return f"{base_url}/{full_path.lstrip('/')}"


def _parse_body(body: bytes) -> tuple[dict, bool]:
    try:
        data = json.loads(body)
        return data, bool(data.get("stream", False))
    except Exception:
        return {}, False


def _extract_request_preview(data: dict, body: bytes) -> str:
    if data:
        try:
            preview = json.dumps(data, ensure_ascii=False)
            return preview[:_MAX_PREVIEW_LEN]
        except Exception:
            pass
    return body[:_MAX_PREVIEW_LEN].decode("utf-8", errors="ignore")


def _extract_model(data: dict) -> str:
    return data.get("model", "") if isinstance(data, dict) else ""


def _safe_json_loads(text: str | bytes) -> Optional[dict]:
    try:
        return json.loads(text)
    except Exception:
        return None


def parse_usage_from_response(data: dict) -> tuple[int, int]:
    usage = data.get("usage", {}) or {}
    prompt = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
    completion = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
    return int(prompt or 0), int(completion or 0)


def _record_request_background(
    fake_key_id: int,
    real_key_id: int,
    provider: str,
    model: str,
    endpoint: str,
    status_code: int,
    latency_ms: int,
    tokens_input: int,
    tokens_output: int,
    request_preview: str,
) -> None:
    async def _do() -> None:
        if "chat/completions" not in endpoint:
            return
        try:
            async with AsyncSessionLocal() as log_db:
                await record_request(
                    log_db, fake_key_id, real_key_id, provider, model, endpoint,
                    status_code, latency_ms, tokens_input, tokens_output, request_preview,
                )
        except Exception:
            pass

    run_in_background(_do())


def _response_headers(response: httpx.Response) -> dict[str, str]:
    drop = {"content-length", "transfer-encoding", "content-encoding"}
    return {k: v for k, v in response.headers.items() if k.lower() not in drop}


async def proxy_request(
    request: Request,
    real_key: RealKey,
    fake_key_id: int,
    full_path: str,
) -> StreamingResponse:
    target_url = _build_target_url(real_key, full_path)
    provider = real_key.provider
    path = full_path
    is_chat = "chat/completions" in path

    real_key_text = get_real_key_decrypted(real_key)

    body = await request.body()
    data, is_stream = _parse_body(body)
    request_preview = _extract_request_preview(data, body) if is_chat else ""
    model = _extract_model(data) if is_chat else ""

    headers = {}
    for key, value in request.headers.items():
        if key.lower() in ("host", "content-length", "authorization"):
            continue
        headers[key] = value
    headers["Authorization"] = f"Bearer {real_key_text}"

    method = request.method
    client = get_http_client()
    start_time = time.time()

    req = client.build_request(method, target_url, headers=headers, content=body)
    response = await client.send(req, stream=True)

    if is_stream and method.upper() == "POST":
        return await _proxy_stream(
            response, fake_key_id, real_key.id, provider, model,
            path, request_preview, start_time, is_chat,
        )
    return await _proxy_non_stream(
        response, fake_key_id, real_key.id, provider, model,
        path, request_preview, start_time, is_chat,
    )


async def _proxy_non_stream(
    response: httpx.Response,
    fake_key_id: int,
    real_key_id: int,
    provider: str,
    model: str,
    endpoint: str,
    request_preview: str,
    start_time: float,
    is_chat: bool,
) -> StreamingResponse:
    chunks: list[bytes] = []

    async def body_generator() -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_bytes():
                if is_chat:
                    chunks.append(chunk)
                yield chunk
        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            tokens_input, tokens_output = 0, 0
            if is_chat:
                body = b"".join(chunks)
                data = _safe_json_loads(body)
                tokens_input, tokens_output = parse_usage_from_response(data) if data else (0, 0)
            _record_request_background(
                fake_key_id, real_key_id, provider, model, endpoint,
                response.status_code, latency_ms, tokens_input, tokens_output, request_preview,
            )
            await response.aclose()

    return StreamingResponse(
        body_generator(),
        status_code=response.status_code,
        media_type=response.headers.get("content-type", "application/json"),
        headers=_response_headers(response),
    )


async def _proxy_stream(
    response: httpx.Response,
    fake_key_id: int,
    real_key_id: int,
    provider: str,
    model: str,
    endpoint: str,
    request_preview: str,
    start_time: float,
    is_chat: bool,
) -> StreamingResponse:
    chunks: list[bytes] = []

    async def event_generator() -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_bytes():
                if is_chat:
                    chunks.append(chunk)
                yield chunk
        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            tokens_input, tokens_output = 0, 0
            if is_chat:
                tokens_input, tokens_output = _extract_stream_usage(chunks)
            _record_request_background(
                fake_key_id, real_key_id, provider, model, endpoint,
                response.status_code, latency_ms, tokens_input, tokens_output, request_preview,
            )
            await response.aclose()

    return StreamingResponse(
        event_generator(),
        status_code=response.status_code,
        media_type="text/event-stream",
        headers=_response_headers(response),
    )


def _extract_stream_usage(chunks: list[bytes]) -> tuple[int, int]:
    if not chunks:
        return 0, 0

    text = b"".join(chunks).decode("utf-8", errors="ignore")
    tokens_input = 0
    tokens_output = 0
    usage_found = False
    output_chars = 0

    for line in text.split("\n"):
        if not line.startswith("data: "):
            continue
        data_str = line[6:].strip()
        if data_str == "[DONE]":
            continue
        data = _safe_json_loads(data_str)
        if not data:
            continue

        u = data.get("usage")
        if u:
            tokens_input = u.get("prompt_tokens", 0) or u.get("input_tokens", 0)
            tokens_output = u.get("completion_tokens", 0) or u.get("output_tokens", 0)
            usage_found = True

        if not usage_found:
            for choice in data.get("choices", []):
                delta = choice.get("delta", {})
                content = delta.get("content", "")
                if content:
                    output_chars += len(content)

    if not usage_found and output_chars:
        tokens_output = max(1, output_chars // 4)

    return int(tokens_input or 0), int(tokens_output or 0)
