import httpx


_TIMEOUT = httpx.Timeout(300.0, connect=10.0, read=300.0, write=30.0)

_LIMITS = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=30.0,
)

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=_LIMITS,
            http2=True,
        )
    return _http_client


async def close_http_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
