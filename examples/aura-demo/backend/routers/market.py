"""Market simulation endpoints. Two independent toggles:
  /market/auto-run  — clock auto-ticking on/off
  /market/auto-fix  — Hermes auto-propose on newly-non-green on/off
Applying trades always stays behind the human gate (approve-batch).
"""
import asyncio
import os
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core import market as M, data_loader

router = APIRouter(prefix="/market", tags=["market"])

_autorun_task: Optional[asyncio.Task] = None


class AutoRunBody(BaseModel):
    on: bool
    interval_sec: Optional[int] = None


class AutoFixBody(BaseModel):
    on: bool


async def _autorun_loop():
    """Ticks the clock every auto_interval_sec while clock.running is on.

    Cancellable via auto-run {on:false} (set_running(false) + task.cancel).
    Loop checks running on each iteration, so a concurrent tick call is safe —
    worst case two ticks advance the day by 2; that is acceptable under the
    idempotent-day contract (spec §12) and SQLite WAL.
    """
    while True:
        clock = M.get_clock()
        if not clock["running"]:
            break
        M.tick(run_monitor=True)
        await asyncio.sleep(max(1, clock["auto_interval_sec"]))


@router.get("/clock")
def clock():
    return M.get_clock()


@router.post("/tick")
def tick():
    return M.tick(run_monitor=True)


@router.post("/advance")
def advance(days: int = Query(..., ge=1, le=500)):
    return M.advance(days, run_monitor=True)


@router.post("/auto-run")
async def auto_run(body: AutoRunBody):
    M.set_running(body.on, interval_sec=body.interval_sec)
    start_autorun_loop() if body.on else stop_autorun_loop()
    return M.get_clock()


def start_autorun_loop():
    """Launch the autorun background task if it isn't already running.

    Idempotent: reuses the module-level `_autorun_task` guard so multiple
    calls (startup event + POST /market/auto-run) never spawn two loops.
    Safe to call from a running asyncio event loop (FastAPI startup handler,
    endpoint handlers). Returns the task (or None if not launched here).
    """
    global _autorun_task
    if _autorun_task is None or _autorun_task.done():
        _autorun_task = asyncio.create_task(_autorun_loop())
        return _autorun_task
    return None


def stop_autorun_loop():
    """Cancel the autorun background task if any. Idempotent."""
    global _autorun_task
    if _autorun_task is not None and not _autorun_task.done():
        _autorun_task.cancel()
    _autorun_task = None


@router.post("/auto-fix")
def auto_fix(body: AutoFixBody):
    return M.set_auto_fix(body.on)


@router.get("/prices")
def prices():
    return data_loader.current_prices()


@router.get("/history")
def history(from_day: int = Query(0), to_day: int = Query(100)):
    return M.history(from_day, to_day)


@router.get("/status")
def status():
    return M.status()


# Apply env defaults on import (idempotent — only flips when env explicitly set).
def _apply_env_defaults():
    if os.environ.get("MARKET_AUTO_RUN", "").lower() in ("1", "true", "on"):
        interval = int(os.environ.get("MARKET_AUTO_INTERVAL_SEC", "5"))
        M.set_running(True, interval_sec=interval)
    if os.environ.get("MARKET_AUTO_FIX", "").lower() in ("1", "true"):
        M.set_auto_fix(True)


try:
    _apply_env_defaults()
except Exception:
    # DB not initialized yet (e.g. fresh import before first build) — skip
    pass