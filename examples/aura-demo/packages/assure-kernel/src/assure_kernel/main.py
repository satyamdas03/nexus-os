"""Standalone ASGI entry point for the ASSURE kernel service."""
from __future__ import annotations

from fastapi import FastAPI

from assure_kernel import __version__ as kernel_version
from assure_kernel.api import router

app = FastAPI(
    title="ASSURE Kernel-as-a-Service",
    description="Deterministic portfolio assurance engine. Stateless. Read-only. Versioned.",
    version=kernel_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    return {
        "service": "assure-kernel",
        "version": kernel_version,
        "docs": "/docs",
        "health": "/v1/health",
    }
