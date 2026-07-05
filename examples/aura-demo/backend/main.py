import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Assure", version="0.1.0")

# In production, CORS should be restricted to the deployed frontend origin.
# Dev keeps permissive origins so local Next.js / Vercel previews work.
_allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "*").split(",")
if _allowed_origins == ["*"]:
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in _allowed_origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials="*" not in allow_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Secret", "Authorization"],
)


from routers import portfolios, audit, actions, admin, hermes, market, evidence, chat, voice, auth, adviser

app.include_router(auth.router)
app.include_router(portfolios.router)
app.include_router(audit.router)
app.include_router(actions.router)
app.include_router(admin.router)
app.include_router(hermes.router)
app.include_router(market.router)
app.include_router(evidence.router)
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(adviser.router)


@app.on_event("startup")
async def _ensure_book_then_autorun():
    """On a fresh deploy (ephemeral disk → empty db) generate the 34k book
    before serving, so the Command Centre loads 34,000 portfolios instead of 0.
    Idempotent: `ensure_book` skips generation when a book already exists, so a
    reboot on a persistent disk preserves the clock day + approved trades.

    Then, if MARKET_AUTO_RUN is truthy, launch the autorun loop. (The env
    default is false.) `_apply_env_defaults` flips clock.running=1 at import
    time but cannot spawn the task (no running loop then); this handler runs
    inside the loop so it can. Idempotent via `start_autorun_loop`'s guard.
    """
    from core import data_loader
    from core.auth import ensure_bootstrap_admin

    data_loader.ensure_book()
    ensure_bootstrap_admin()
    if os.environ.get("MARKET_AUTO_RUN", "").lower() in ("1", "true", "on"):
        market.start_autorun_loop()


@app.get("/health")
def health():
    return {"status": "ok"}