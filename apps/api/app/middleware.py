"""ASGI middleware stack — IP-based rate limiting via Redis sliding window."""
from __future__ import annotations

import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.cache import redis
from app.config import get_settings

log = logging.getLogger("api.middleware")

# Paths guarded by per-IP rate limiting (prefix match).
_RATE_LIMITED_PREFIXES = (
    "/auth/",
    "/api/auth/",
    "/agent/chat",
    "/api/agent/chat",
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-IP rate limiter backed by Redis.

    Each IP gets a counter keyed by ``rl:ip:<ip>:<window_bucket>``.
    The window bucket is ``epoch_seconds // window_seconds`` so it resets
    every full window without needing a separate cleanup job.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not any(path.startswith(p) or path == p.rstrip("/") for p in _RATE_LIMITED_PREFIXES):
            return await call_next(request)

        settings = get_settings()
        window = settings.ip_rate_limit_window_seconds
        limit = settings.ip_rate_limit_requests
        ip = _client_ip(request)

        try:
            import time
            bucket = int(time.time()) // window
            key = f"rl:ip:{ip}:{bucket}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window * 2)
            if count > limit:
                log.warning("IP rate limit exceeded ip=%s path=%s count=%d", ip, path, count)
                return JSONResponse(
                    status_code=429,
                    content={"error": {"code": "ip_rate_limited", "message": "Too many requests from this IP.", "details": {}}},
                )
        except Exception:
            log.debug("IP rate limit check failed — allowing request", exc_info=True)

        return await call_next(request)
