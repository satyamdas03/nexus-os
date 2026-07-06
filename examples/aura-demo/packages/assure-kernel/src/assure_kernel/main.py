"""Standalone ASGI entry point for the ASSURE kernel service."""
from __future__ import annotations

import logging
import os
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import APIKeyHeader

from assure_kernel import __version__ as kernel_version
from assure_kernel.api import router

# Configure structured stdout logging for Docker / container environments.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("assure-kernel")

API_KEY = os.environ.get("ASSURE_KERNEL_API_KEY")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Depends(_api_key_header)) -> None:
    """Pluggable API key guard.

    When ASSURE_KERNEL_API_KEY is unset the middleware is a no-op, preserving
    zero-config local usage. When it is set, every /v1/* call must carry the
    same key in the X-API-Key header.
    """
    if API_KEY and api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )


app = FastAPI(
    title="ASSURE Kernel-as-a-Service",
    description="Deterministic portfolio assurance engine. Stateless. Read-only. Versioned.",
    version=kernel_version,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """Lightweight request/response logging with latency timing."""
    request_id = request.headers.get("X-Request-ID") or uuid4().hex[:12]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(router, dependencies=[Depends(require_api_key)])


@app.get("/")
def root() -> dict:
    return {
        "service": "assure-kernel",
        "version": kernel_version,
        "docs": "/docs",
        "health": "/v1/health",
    }
