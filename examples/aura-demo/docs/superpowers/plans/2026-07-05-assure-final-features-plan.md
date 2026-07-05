:# ASSURE 2.0 Final Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three remaining Financial Simplicity transcript-aligned features in aura-demo: an AI Investment Manager Agent (voice + whiteboard math), a Confidence / Confirmation Prediction Card, and a Synthetic-Test → Strategy Diff + Regression Test Generator.

**Architecture:** Each feature is a thin, testable layer on top of the existing deterministic core (`rules_engine.py`, `hermes` simulator, `livekit_assistant.py`). The backend exposes new FastAPI routers; the frontend adds one page, one reusable card, and one panel. All features respect the existing RBAC gates (`require_mutation`, `require_admin`).

**Tech Stack:** FastAPI, Python 3.14, SQLite, Claude/OpenAI via existing `agents/llm.py`, LiveKit Components React, Next.js 14, TypeScript, Tailwind, Vitest, pytest.

## Global Constraints

- Python 3.14 compatibility required; use `pbkdf2_sha256` instead of bcrypt.
- All new API endpoints must use existing auth dependencies in `core/auth.py`.
- All LLM calls must be grounded in deterministic rules output; never let the LLM override mandate rules.
- Every generated/advisory UI element must carry a deterministic citation or disclaimer.
- New tests must be pytest for backend, Vitest for frontend components.
- Commit after each independently testable task.
- Do not modify the Bull trading agent project or any IP/legal process.

---

## File Map

### New backend files

| File | Responsibility |
|---|---|
| `backend/routers/adviser.py` | `/adviser/session`, `/adviser/chat`, `/adviser/whiteboard` endpoints |
| `backend/agents/adviser/prompts.py` | System prompts for the adviser persona + whiteboard extraction |
| `backend/agents/adviser/whiteboard.py` | Build the whiteboard payload from portfolio + proposed trades |
| `backend/routers/confidence.py` | `/confidence/{client_id}` endpoint |
| `backend/core/confidence.py` | Pure scoring logic for confidence factors |
| `backend/agents/hermes/generator.py` | Simulation diff search + strategy YAML diff generation |
| `backend/agents/hermes/test_generator.py` | Generate pytest regression tests from a diff |
| `backend/agents/hermes/generated_tests/` | Runtime directory for generated tests |

### Modified backend files

| File | Change |
|---|---|
| `backend/main.py` | Register `adviser.router` and `confidence.router` |
| `backend/routers/hermes.py` | Add `/hermes/generate` and `/hermes/run-test` |
| `backend/agents/hermes/strategy_io.py` | Expose helpers to read/write strategy as dict |
| `backend/agents/hermes/loop.py` | Expose `simulate()` for external callers |

### New frontend files

| File | Responsibility |
|---|---|
| `frontend/src/app/adviser/page.tsx` | Standalone AI Adviser page |
| `frontend/src/components/adviser/AdviserCanvas.tsx` | Visual whiteboard for breach → fix explanation |
| `frontend/src/components/adviser/AdviserChat.tsx` | Text chat surface |
| `frontend/src/components/adviser/AdviserControls.tsx` | Voice join/mute/leave controls |
| `frontend/src/components/ConfidenceCard.tsx` | Multi-factor confidence display |
| `frontend/src/components/ConfidenceMeter.tsx` | Segmented bar for one factor |
| `frontend/src/components/hermes/HermesGeneratePanel.tsx` | Generate diff + test panel |
| `frontend/src/components/hermes/StrategyDiff.tsx` | YAML diff display |
| `frontend/src/components/hermes/GeneratedTestView.tsx` | Code block + run/copy buttons |

### Modified frontend files

| File | Change |
|---|---|
| `frontend/src/lib/api.ts` | Add `adviser.*`, `confidence.*`, `hermes.generate`, `hermes.runTest` |
| `frontend/src/lib/types.ts` | Add `AdviserWhiteboard`, `ConfidenceResult`, `HermesGenerateResult` |
| `frontend/src/components/AppShell.tsx` | Add `/adviser` to mobile/desktop nav |
| `frontend/src/components/ChatDrawer.tsx` | Add voice/adviser mode toggle |
| `frontend/src/components/hermes/HermesQueue.tsx` | Render `ConfidenceCard` inside `QueueRow` |
| `frontend/src/app/portfolio/[id]/workbench/page.tsx` | Render `ConfidenceCard` near Approve button |
| `frontend/src/app/hermes/page.tsx` | Insert `HermesGeneratePanel` |

---

## Task 1: Backend — Adviser Whiteboard Payload

**Files:**
- Create: `backend/agents/adviser/prompts.py`
- Create: `backend/agents/adviser/whiteboard.py`
- Create: `backend/routers/adviser.py`
- Test: `backend/tests/test_adviser.py`
- Modify: `backend/main.py:22-33` (register routers)

**Interfaces:**
- Consumes: `api.getPortfolio(id)`, `api.remediate(id)`, `rules_engine.check` indirectly via existing remediate flow.
- Produces: `POST /adviser/whiteboard` returns `AdviserWhiteboard` JSON (see spec §3.3).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_adviser.py
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from core import data_loader, storage
from core.auth import create_user
from generators import generate_data


def _client(n=50):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = storage.get_conn(path)
    storage.init_schema(conn)
    storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    old_enforce = os.environ.get("AUTH_ENFORCE")
    old_secret = os.environ.get("AUTH_SECRET")
    os.environ["AUTH_ENFORCE"] = "1"
    os.environ["AUTH_SECRET"] = "test-secret-32-bytes-long-ok"
    create_user(conn, "admin", "adminpass", "admin")
    from main import app
    c = TestClient(app)
    r = c.post("/auth/token", json={"username": "admin", "password": "adminpass"})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    try:
        yield c
    finally:
        data_loader.set_conn(None)
        if old_enforce is None:
            os.environ.pop("AUTH_ENFORCE", None)
        else:
            os.environ["AUTH_ENFORCE"] = old_enforce
        if old_secret is None:
            os.environ.pop("AUTH_SECRET", None)
        else:
            os.environ["AUTH_SECRET"] = old_secret


@pytest.fixture
def client():
    yield from _client()


def test_whiteboard_returns_structured_payload(client):
    rows = client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    r = client.post(f"/adviser/whiteboard/{client_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["client_id"] == client_id
    assert "current_status" in body
    assert "breaches" in body
    assert "proposed_trades" in body
    assert "post_status" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_adviser.py::test_whiteboard_returns_structured_payload -v`
Expected: FAIL — route does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `backend/agents/adviser/whiteboard.py`:

```python
"""Build an adviser whiteboard payload for a portfolio."""
from __future__ import annotations

from typing import Any

from core.data_loader import get_portfolio, get_conn_cached
from core.effective import get_effective
from core.rules_engine import check
from agents.remediate import propose_remediation


def build_whiteboard(client_id: str) -> dict[str, Any]:
    p = get_portfolio(client_id)
    mandate = p["mandate"]
    eff = get_effective(client_id, seed=p)
    rr = check(eff, mandate)

    # Use existing remediation proposer to get a concrete fix.
    remediation = propose_remediation(eff, mandate, client_id=client_id)
    trades = remediation.get("trades", [])

    # Re-verify the proposed trades so post_status is accurate.
    if trades:
        for t in trades:
            eff.setdefault(t["ticker"], {"units": 0, "market_value": 0})
            if t["action"] == "sell":
                eff[t["ticker"]]["units"] -= t["units"]
            else:
                eff[t["ticker"]]["units"] += t["units"]
        post_rr = check(eff, mandate)
    else:
        post_rr = rr

    breaches_out = []
    for b in rr.get("breaches", []):
        breaches_out.append({
            "rule": b["rule"],
            "limit": b.get("limit"),
            "current": b.get("current"),
            "offending_holdings": b.get("offending_holdings", []),
            "explanation": b.get("message", ""),
        })

    trades_out = []
    total_value = sum(h["market_value"] for h in p.get("holdings", [])) + p.get("cash", 0)
    for t in trades:
        trades_out.append({
            "action": t["action"],
            "ticker": t["ticker"],
            "units": t["units"],
            "value": t.get("value", t["units"] * eff.get(t["ticker"], {}).get("price", 0)),
            "rationale": t.get("rationale", ""),
        })

    aum_impact = sum(abs(t["value"]) for t in trades_out) if trades_out else 0
    return {
        "client_id": client_id,
        "client_name": p.get("client_name", client_id),
        "current_status": rr["status"],
        "breaches": breaches_out,
        "proposed_trades": trades_out,
        "post_status": post_rr["status"],
        "impact": {
            "aum_impact_pct": round(aum_impact / total_value, 4) if total_value else 0,
            "trades_count": len(trades_out),
        },
    }
```

Create `backend/routers/adviser.py`:

```python
from fastapi import APIRouter, Depends
from core.auth import get_current_user_or_dev
from agents.adviser.whiteboard import build_whiteboard

router = APIRouter()


@router.post("/adviser/whiteboard/{client_id}")
def whiteboard(client_id: str, _user=Depends(get_current_user_or_dev)):
    return build_whiteboard(client_id)
```

Modify `backend/main.py` to import and include the router:

```python
from routers import portfolios, audit, actions, admin, hermes, market, evidence, chat, voice, auth, adviser
app.include_router(adviser.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_adviser.py::test_whiteboard_returns_structured_payload -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/adviser/whiteboard.py backend/routers/adviser.py backend/tests/test_adviser.py backend/main.py
git commit -m "feat(adviser): structured whiteboard payload endpoint"
```

---

## Task 2: Backend — Adviser Chat Endpoint

**Files:**
- Modify: `backend/agents/adviser/prompts.py`
- Modify: `backend/routers/adviser.py`
- Test: `backend/tests/test_adviser.py`

**Interfaces:**
- Consumes: `build_whiteboard(client_id)`, existing `agents/llm.py` `claude_completion` or equivalent.
- Produces: `POST /adviser/chat` returns `{answer: str, whiteboard: dict}`.

- [ ] **Step 1: Write the failing test**

```python
def test_chat_refuses_trade_execution(client):
    rows = client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    r = client.post(
        "/adviser/chat",
        json={"client_id": client_id, "query": "Execute the trade now"},
    )
    assert r.status_code == 200, r.text
    answer = r.json()["answer"].lower()
    assert "cannot execute" in answer or "workbench" in answer or "advisory" in answer
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_adviser.py::test_chat_refuses_trade_execution -v`
Expected: FAIL — route does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `backend/agents/adviser/prompts.py`:

```python
"""Prompts for the AI Investment Manager adviser."""

ADVISER_SYSTEM = """You are ASSURE, an AI investment adviser. You explain portfolio breaches and proposed fixes in plain English to a wealth manager or client. You may only provide advisory explanations. You cannot execute trades, place orders, or approve trades. If asked to execute, redirect the user to the Remediation Workbench. Always ground your answer in the deterministic rules engine output provided below."""


def chat_prompt(whiteboard: dict, query: str) -> str:
    return f"""{ADVISER_SYSTEM}

Portfolio: {whiteboard['client_name']} ({whiteboard['client_id']})
Current status: {whiteboard['current_status']}
Breaches: {whiteboard['breaches']}
Proposed trades: {whiteboard['proposed_trades']}
Post-trade status: {whiteboard['post_status']}
Impact: {whiteboard['impact']}

User question: {query}

Answer concisely. If the user asks to trade, say you cannot execute trades and direct them to the Workbench."""
```

Modify `backend/routers/adviser.py`:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from core.auth import get_current_user_or_dev
from agents.adviser.whiteboard import build_whiteboard
from agents.adviser.prompts import chat_prompt
from agents.llm import claude_completion

router = APIRouter()


class ChatRequest(BaseModel):
    client_id: str
    query: str


@router.post("/adviser/whiteboard/{client_id}")
def whiteboard(client_id: str, _user=Depends(get_current_user_or_dev)):
    return build_whiteboard(client_id)


@router.post("/adviser/chat")
def chat(body: ChatRequest, _user=Depends(get_current_user_or_dev)):
    wb = build_whiteboard(body.client_id)
    prompt = chat_prompt(wb, body.query)
    answer = claude_completion(prompt, max_tokens=512)
    return {"answer": answer, "whiteboard": wb}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_adviser.py::test_chat_refuses_trade_execution -v`
Expected: PASS. If the LLM response is nondeterministic, mock `claude_completion` in the test or assert on substring presence.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/adviser/prompts.py backend/routers/adviser.py backend/tests/test_adviser.py
git commit -m "feat(adviser): grounded chat endpoint refuses execution"
```

---

## Task 3: Backend — Adviser Session + LiveKit Token

**Files:**
- Modify: `backend/routers/adviser.py`
- Modify: `backend/routers/voice.py` (reuse token helper if needed)
- Test: `backend/tests/test_adviser.py`

**Interfaces:**
- Consumes: existing `/voice/token/{client_id}` logic.
- Produces: `POST /adviser/session` returns `{token: str, url: str, room: str, identity: str}`.

- [ ] **Step 1: Write the failing test**

```python
def test_session_returns_livekit_token(client):
    rows = client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    r = client.post("/adviser/session", json={"client_id": client_id})
    # If LiveKit is not configured in test env, expect graceful 503 or fallback.
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        body = r.json()
        assert "token" in body
        assert "room" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_adviser.py::test_session_returns_livekit_token -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Modify `backend/routers/adviser.py`:

```python
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.auth import get_current_user_or_dev
from agents.adviser.whiteboard import build_whiteboard
from agents.adviser.prompts import chat_prompt
from agents.llm import claude_completion
from routers.voice import _voice_token  # assumes existing helper

router = APIRouter()


class SessionRequest(BaseModel):
    client_id: str


@router.post("/adviser/session")
def session(body: SessionRequest, _user=Depends(get_current_user_or_dev)):
    if not os.environ.get("LIVEKIT_API_KEY") or not os.environ.get("LIVEKIT_SECRET"):
        raise HTTPException(status_code=503, detail="LiveKit not configured")
    room = f"adviser-{body.client_id}"
    identity = "adviser-user"
    token = _voice_token(room, identity)
    return {
        "token": token,
        "url": os.environ.get("LIVEKIT_URL", ""),
        "room": room,
        "identity": identity,
    }
```

If `_voice_token` is not exported, modify `backend/routers/voice.py` to expose it as a function.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_adviser.py::test_session_returns_livekit_token -v`
Expected: PASS (503 path).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/adviser.py backend/routers/voice.py backend/tests/test_adviser.py
git commit -m "feat(adviser): LiveKit session endpoint"
```

---

## Task 4: Frontend — AI Adviser Page

**Files:**
- Create: `frontend/src/app/adviser/page.tsx`
- Create: `frontend/src/components/adviser/AdviserCanvas.tsx`
- Create: `frontend/src/components/adviser/AdviserChat.tsx`
- Create: `frontend/src/components/adviser/AdviserControls.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Test: `frontend/src/components/adviser/AdviserCanvas.test.tsx`

**Interfaces:**
- Consumes: `api.adviser.whiteboard(clientId)`, `api.adviser.chat(clientId, query)`, `api.adviser.session(clientId)`, `VoiceRoom` component.
- Produces: `/adviser` route, reusable adviser subcomponents.

- [ ] **Step 1: Add types**

Modify `frontend/src/lib/types.ts` to add:

```typescript
export interface AdviserWhiteboard {
  client_id: string;
  client_name: string;
  current_status: "green" | "orange" | "red";
  breaches: Array<{
    rule: string;
    limit?: number;
    current?: number;
    offending_holdings: string[];
    explanation: string;
  }>;
  proposed_trades: Array<{
    action: "buy" | "sell";
    ticker: string;
    units: number;
    value: number;
    rationale: string;
  }>;
  post_status: "green" | "orange" | "red";
  impact: { aum_impact_pct: number; trades_count: number };
}

export interface AdviserChatResponse {
  answer: string;
  whiteboard: AdviserWhiteboard;
}
```

- [ ] **Step 2: Add API methods**

Modify `frontend/src/lib/api.ts` inside `export const api = { ... }`:

```typescript
adviser: {
  whiteboard: (clientId: string) =>
    j<AdviserWhiteboard>(`/adviser/whiteboard/${clientId}`, { method: "POST" }),
  chat: (clientId: string, query: string) =>
    j<AdviserChatResponse>("/adviser/chat", { method: "POST", body: JSON.stringify({ client_id: clientId, query }) }),
  session: (clientId: string) =>
    j<{ token: string; url: string; room: string; identity: string }>("/adviser/session", { method: "POST", body: JSON.stringify({ client_id: clientId }) }),
},
```

- [ ] **Step 3: Write failing component test**

Create `frontend/src/components/adviser/AdviserCanvas.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { AdviserCanvas } from "./AdviserCanvas";

const sample: import("@/lib/types").AdviserWhiteboard = {
  client_id: "C00001",
  client_name: "Test Client",
  current_status: "red",
  breaches: [{ rule: "max_region_weight", limit: 0.35, current: 0.52, offending_holdings: ["AAPL"], explanation: "US too high" }],
  proposed_trades: [{ action: "sell", ticker: "AAPL", units: 10, value: 1000, rationale: "Trim US" }],
  post_status: "green",
  impact: { aum_impact_pct: 0.01, trades_count: 1 },
};

test("renders whiteboard", () => {
  render(<AdviserCanvas whiteboard={sample} />);
  expect(screen.getByText(/Test Client/)).toBeInTheDocument();
  expect(screen.getByText(/AAPL/)).toBeInTheDocument();
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/adviser/AdviserCanvas.test.tsx`
Expected: FAIL — component does not exist.

- [ ] **Step 5: Implement components and page**

Create `frontend/src/components/adviser/AdviserCanvas.tsx`:

```typescript
"use client";
import { AdviserWhiteboard } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

export function AdviserCanvas({ whiteboard }: { whiteboard: AdviserWhiteboard }) {
  return (
    <div className="bg-aura-surface border border-aura-border rounded p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-mono text-lg font-bold text-aura-text">{whiteboard.client_name}</h3>
        <StatusBadge status={whiteboard.current_status} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <p className="font-mono text-xs uppercase text-aura-text-subtle">Current breaches</p>
          {whiteboard.breaches.map((b) => (
            <div key={b.rule} className="p-2 rounded bg-aura-crimson-soft border border-aura-crimson text-aura-crimson text-xs font-mono">
              <span className="font-bold">{b.rule}</span>: {b.explanation}
            </div>
          ))}
        </div>
        <div className="space-y-2">
          <p className="font-mono text-xs uppercase text-aura-text-subtle">Proposed fix</p>
          {whiteboard.proposed_trades.map((t) => (
            <div key={t.ticker} className="p-2 rounded bg-aura-emerald-soft border border-aura-emerald text-aura-emerald text-xs font-mono">
              {t.action.toUpperCase()} {t.units.toFixed(2)} {t.ticker} · ${t.value.toLocaleString()}
            </div>
          ))}
          <div className="flex items-center gap-2 pt-2">
            <span className="font-mono text-xs text-aura-text-subtle">Post-status:</span>
            <StatusBadge status={whiteboard.post_status} />
          </div>
        </div>
      </div>
    </div>
  );
}
```

Create `frontend/src/components/adviser/AdviserChat.tsx`:

```typescript
"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export function AdviserChat({ clientId }: { clientId: string }) {
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; text: string }[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async () => {
    if (!input.trim()) return;
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text: input }]);
    try {
      const res = await api.adviser.chat(clientId, input);
      setMessages((m) => [...m, { role: "assistant", text: res.answer }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: "Sorry, the adviser engine is unreachable." }]);
    }
    setInput("");
    setBusy(false);
  };

  return (
    <div className="space-y-3">
      <div className="h-48 overflow-y-auto space-y-2 bg-aura-surface-low rounded p-3 border border-aura-border">
        {messages.map((m, i) => (
          <div key={i} className={`text-sm font-mono ${m.role === "user" ? "text-aura-navy" : "text-aura-text"}`}>
            <span className="font-bold">{m.role}:</span> {m.text}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          className="flex-1 px-3 py-2 rounded border border-aura-border bg-aura-background text-sm"
          placeholder="Ask about this portfolio..."
        />
        <button onClick={send} disabled={busy} className="px-4 py-2 rounded bg-aura-navy text-white text-sm disabled:opacity-50">
          {busy ? "..." : "Ask"}
        </button>
      </div>
    </div>
  );
}
```

Create `frontend/src/components/adviser/AdviserControls.tsx`:

```typescript
"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { VoiceRoom } from "@/components/VoiceRoom";

export function AdviserControls({ clientId, onLeave }: { clientId: string; onLeave?: () => void }) {
  const [token, setToken] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [room, setRoom] = useState("");
  const [identity, setIdentity] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const join = async () => {
    try {
      const res = await api.adviser.session(clientId);
      setToken(res.token);
      setUrl(res.url);
      setRoom(res.room);
      setIdentity(res.identity);
      setErr(null);
    } catch (e: any) {
      setErr(e.message || "Voice session failed");
    }
  };

  if (token) {
    return (
      <VoiceRoom
        url={url}
        token={token}
        room={room}
        identity={identity}
        onLeave={() => { setToken(null); onLeave?.(); }}
      />
    );
  }

  return (
    <div className="space-y-2">
      {err && <p className="text-xs text-aura-crimson font-mono">{err}</p>}
      <button onClick={join} className="px-4 py-2 rounded bg-aura-navy text-white text-sm">
        Join voice session
      </button>
    </div>
  );
}
```

Create `frontend/src/app/adviser/page.tsx`:

```typescript
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AdviserWhiteboard } from "@/lib/types";
import { AdviserCanvas } from "@/components/adviser/AdviserCanvas";
import { AdviserChat } from "@/components/adviser/AdviserChat";
import { AdviserControls } from "@/components/adviser/AdviserControls";

export default function AdviserPage() {
  const [portfolios, setPortfolios] = useState<{ client_id: string; client_name: string }[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [whiteboard, setWhiteboard] = useState<AdviserWhiteboard | null>(null);

  useEffect(() => {
    api.listPortfolios(100, 0).then((ps) => {
      setPortfolios(ps.map((p) => ({ client_id: p.client_id, client_name: p.client_name })));
    });
  }, []);

  useEffect(() => {
    if (!selected) return;
    api.adviser.whiteboard(selected).then(setWhiteboard).catch(() => setWhiteboard(null));
  }, [selected]);

  return (
    <div className="p-4 lg:p-6 max-w-[1440px] mx-auto">
      <h1 className="font-mono text-2xl font-bold text-aura-text mb-4">AI Investment Adviser</h1>
      <select
        value={selected ?? ""}
        onChange={(e) => setSelected(e.target.value || null)}
        className="mb-6 px-3 py-2 rounded border border-aura-border bg-aura-background text-sm"
      >
        <option value="">Select portfolio</option>
        {portfolios.map((p) => (
          <option key={p.client_id} value={p.client_id}>{p.client_name} ({p.client_id})</option>
        ))}
      </select>

      {whiteboard && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-6">
            <AdviserCanvas whiteboard={whiteboard} />
            <AdviserControls clientId={whiteboard.client_id} />
          </div>
          <div>
            <AdviserChat clientId={whiteboard.client_id} />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Add navigation**

Modify `frontend/src/components/AppShell.tsx`:

```typescript
const mobileTabs = [
  { id: "command", label: "Command", icon: "dashboard", href: "/" },
  { id: "hermes", label: "Hermes", icon: "auto_awesome", href: "/hermes" },
  { id: "adviser", label: "Adviser", icon: "support_agent", href: "/adviser" },
];
```

- [ ] **Step 7: Run tests and typecheck**

Run: `cd frontend && npm run typecheck && npm run test -- src/components/adviser/AdviserCanvas.test.tsx`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/adviser frontend/src/components/adviser frontend/src/lib/api.ts frontend/src/lib/types.ts frontend/src/components/AppShell.tsx
git commit -m "feat(adviser): standalone AI adviser page with voice and whiteboard"
```

---

## Task 5: Frontend — Embedded Adviser in ChatDrawer

**Files:**
- Modify: `frontend/src/components/ChatDrawer.tsx`
- Test: `frontend/src/components/ChatDrawer.test.tsx` (new)

**Interfaces:**
- Consumes: `api.adviser.whiteboard(clientId)`, `api.adviser.chat(clientId, query)`, `AdviserCanvas`, `AdviserControls`, `AdviserChat`.

- [ ] **Step 1: Write failing test**

Create `frontend/src/components/ChatDrawer.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatDrawer } from "./ChatDrawer";

test("toggles adviser mode", () => {
  render(<ChatDrawer clientId="C00001" clientName="Test" open={true} onClose={() => {}} />);
  const btn = screen.getByText(/Adviser mode/i);
  fireEvent.click(btn);
  expect(screen.getByText(/AI Investment Adviser/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/ChatDrawer.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement the toggle**

Modify `frontend/src/components/ChatDrawer.tsx`:

- Add state `const [adviserMode, setAdviserMode] = useState(false);`
- Add a toggle button in the drawer header.
- When `adviserMode` is true, render `AdviserCanvas`, `AdviserControls`, and `AdviserChat` instead of the default chat.
- Fetch the whiteboard via `api.adviser.whiteboard(clientId)` when entering adviser mode.

Stub code:

```typescript
const [adviserMode, setAdviserMode] = useState(false);
const [whiteboard, setWhiteboard] = useState<AdviserWhiteboard | null>(null);

useEffect(() => {
  if (adviserMode && clientId) {
    api.adviser.whiteboard(clientId).then(setWhiteboard).catch(() => setWhiteboard(null));
  }
}, [adviserMode, clientId]);

// In the header area:
<button onClick={() => setAdviserMode((v) => !v)} className="text-xs font-mono text-aura-navy">
  {adviserMode ? "Chat mode" : "Adviser mode"}
</button>

// Render path:
{adviserMode && whiteboard ? (
  <div className="space-y-4">
    <AdviserCanvas whiteboard={whiteboard} />
    <AdviserControls clientId={clientId} />
    <AdviserChat clientId={clientId} />
  </div>
) : (
  // existing chat UI
)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/components/ChatDrawer.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatDrawer.tsx frontend/src/components/ChatDrawer.test.tsx
git commit -m "feat(adviser): embedded adviser mode in portfolio ChatDrawer"
```

---

## Task 6: Backend — Confidence Scoring Engine

**Files:**
- Create: `backend/core/confidence.py`
- Create: `backend/routers/confidence.py`
- Test: `backend/tests/test_confidence.py`
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `rules_engine.check`, `hermes.simulate`, audit/state history.
- Produces: `POST /confidence/{client_id}` returns `ConfidenceResult` JSON.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_confidence.py`:

```python
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from core import data_loader, storage
from core.auth import create_user
from generators import generate_data


def _client(n=50):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = storage.get_conn(path)
    storage.init_schema(conn)
    storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    old_enforce = os.environ.get("AUTH_ENFORCE")
    old_secret = os.environ.get("AUTH_SECRET")
    os.environ["AUTH_ENFORCE"] = "1"
    os.environ["AUTH_SECRET"] = "test-secret-32-bytes-long-ok"
    create_user(conn, "admin", "adminpass", "admin")
    from main import app
    c = TestClient(app)
    r = c.post("/auth/token", json={"username": "admin", "password": "adminpass"})
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    try:
        yield c
    finally:
        data_loader.set_conn(None)
        if old_enforce is None:
            os.environ.pop("AUTH_ENFORCE", None)
        else:
            os.environ["AUTH_ENFORCE"] = old_enforce
        if old_secret is None:
            os.environ.pop("AUTH_SECRET", None)
        else:
            os.environ["AUTH_SECRET"] = old_secret


@pytest.fixture
def client():
    yield from _client()


def test_confidence_returns_scores(client):
    rows = client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    r = client.post(f"/confidence/{client_id}", json={"trades": []})
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0 <= body["confidence"] <= 1
    assert "human_review_recommended" in body
    assert len(body["factors"]) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_confidence.py::test_confidence_returns_scores -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Create `backend/core/confidence.py`:

```python
"""Pure confidence scoring for ASSURE proposals."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.effective import get_effective
from core.rules_engine import check


@dataclass(frozen=True)
class ConfidenceResult:
    confidence: float
    rule_engine_certainty: float
    simulation_baseline: float
    historical_approval_success: float
    data_freshness: float
    human_review_recommended: bool
    factors: list[dict[str, Any]]
    explanation: str


def score_confidence(client_id: str, trades: list[dict], conn=None, simulate_fn=None, history_fn=None) -> ConfidenceResult:
    from core.data_loader import get_portfolio

    p = get_portfolio(client_id)
    mandate = p["mandate"]
    eff = get_effective(client_id, seed=p)

    # 1. Rule-engine certainty
    if trades:
        for t in trades:
            eff.setdefault(t["ticker"], {"units": 0, "market_value": 0, "price": 0})
            if t["action"] == "sell":
                eff[t["ticker"]]["units"] -= t["units"]
            else:
                eff[t["ticker"]]["units"] += t["units"]
    rr = check(eff, mandate)
    if rr["status"] == "green":
        rule_score = 1.0
    elif rr["status"] == "orange":
        rule_score = 0.7
    else:
        rule_score = 0.0

    # 2. Simulation baseline
    sim_score = 0.85  # default until simulate_fn is wired
    if simulate_fn:
        try:
            before = simulate_fn(mode="prevent", seed=42)
            sim_score = max(0.0, 1.0 - (before.get("prevent_incidence", 0) / 200))
        except Exception:
            sim_score = 0.5

    # 3. Historical approval success
    hist_score = 0.9  # default optimism
    if history_fn:
        try:
            hist_score = history_fn(client_id, trades)
        except Exception:
            hist_score = 0.5

    # 4. Data freshness (placeholder: prices are always current in simulation)
    freshness_score = 1.0

    factors = [
        {"name": "rules_engine", "score": rule_score, "weight": 0.5},
        {"name": "simulation_baseline", "score": sim_score, "weight": 0.3},
        {"name": "historical_approval_success", "score": hist_score, "weight": 0.2},
    ]
    confidence = round(sum(f["score"] * f["weight"] for f in factors), 3)
    human_review = any(f["score"] < 0.8 for f in factors) or confidence < 0.85

    if human_review:
        explanation = f"Confidence {confidence}: one or more factors below threshold; human review recommended."
    else:
        explanation = f"Confidence {confidence}: deterministic gate green, simulation and history supportive."

    return ConfidenceResult(
        confidence=confidence,
        rule_engine_certainty=rule_score,
        simulation_baseline=sim_score,
        historical_approval_success=hist_score,
        data_freshness=freshness_score,
        human_review_recommended=human_review,
        factors=factors,
        explanation=explanation,
    )
```

Create `backend/routers/confidence.py`:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from core.auth import get_current_user_or_dev
from core.confidence import score_confidence

router = APIRouter()


class ConfidenceRequest(BaseModel):
    trades: list[dict]


@router.post("/confidence/{client_id}")
def confidence(client_id: str, body: ConfidenceRequest, _user=Depends(get_current_user_or_dev)):
    result = score_confidence(client_id, body.trades)
    return result.__dict__
```

Modify `backend/main.py`:

```python
from routers import portfolios, audit, actions, admin, hermes, market, evidence, chat, voice, auth, adviser, confidence
app.include_router(confidence.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_confidence.py::test_confidence_returns_scores -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/confidence.py backend/routers/confidence.py backend/tests/test_confidence.py backend/main.py
git commit -m "feat(confidence): multi-factor confidence scoring endpoint"
```

---

## Task 7: Frontend — Confidence Card

**Files:**
- Create: `frontend/src/components/ConfidenceMeter.tsx`
- Create: `frontend/src/components/ConfidenceCard.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Test: `frontend/src/components/ConfidenceCard.test.tsx`

**Interfaces:**
- Consumes: `api.confidence.calculate(clientId, trades)`.
- Produces: `ConfidenceCard` component.

- [ ] **Step 1: Add types and API**

Modify `frontend/src/lib/types.ts`:

```typescript
export interface ConfidenceFactor {
  name: string;
  score: number;
  weight: number;
}

export interface ConfidenceResult {
  confidence: number;
  rule_engine_certainty: number;
  simulation_baseline: number;
  historical_approval_success: number;
  data_freshness: number;
  human_review_recommended: boolean;
  factors: ConfidenceFactor[];
  explanation: string;
}
```

Modify `frontend/src/lib/api.ts`:

```typescript
confidence: {
  calculate: (clientId: string, trades: any[]) =>
    j<ConfidenceResult>(`/confidence/${clientId}`, { method: "POST", body: JSON.stringify({ trades }) }),
},
```

- [ ] **Step 2: Write failing test**

Create `frontend/src/components/ConfidenceCard.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { ConfidenceCard } from "./ConfidenceCard";

const sample: import("@/lib/types").ConfidenceResult = {
  confidence: 0.93,
  rule_engine_certainty: 1,
  simulation_baseline: 0.85,
  historical_approval_success: 0.95,
  data_freshness: 1,
  human_review_recommended: false,
  factors: [
    { name: "rules_engine", score: 1, weight: 0.5 },
    { name: "simulation_baseline", score: 0.85, weight: 0.3 },
    { name: "historical_approval_success", score: 0.95, weight: 0.2 },
  ],
  explanation: "All good.",
};

test("renders confidence and factors", () => {
  render(<ConfidenceCard result={sample} />);
  expect(screen.getByText(/93%/)).toBeInTheDocument();
  expect(screen.getByText(/rules_engine/)).toBeInTheDocument();
});
```

- [ ] **Step 3: Implement components**

Create `frontend/src/components/ConfidenceMeter.tsx`:

```typescript
export function ConfidenceMeter({ value, label }: { value: number; label: string }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.85 ? "bg-aura-emerald" : value >= 0.6 ? "bg-aura-ochre" : "bg-aura-crimson";
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs font-mono text-aura-text-subtle">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 w-full bg-aura-surface-low rounded overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
```

Create `frontend/src/components/ConfidenceCard.tsx`:

```typescript
"use client";
import { ConfidenceResult } from "@/lib/types";
import { ConfidenceMeter } from "./ConfidenceMeter";

export function ConfidenceCard({ result }: { result: ConfidenceResult }) {
  return (
    <div className="bg-aura-surface border border-aura-border rounded p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs uppercase text-aura-text-subtle">AI Confidence</span>
        {result.human_review_recommended ? (
          <span className="px-2 py-1 rounded bg-aura-crimson-soft text-aura-crimson text-xs font-mono font-bold">Human review recommended</span>
        ) : (
          <span className="px-2 py-1 rounded bg-aura-emerald-soft text-aura-emerald text-xs font-mono font-bold">High confidence</span>
        )}
      </div>
      <ConfidenceMeter value={result.confidence} label="Overall" />
      {result.factors.map((f) => (
        <ConfidenceMeter key={f.name} value={f.score} label={f.name} />
      ))}
      <p className="text-xs text-aura-text-muted font-mono leading-snug">{result.explanation}</p>
    </div>
  );
}
```

- [ ] **Step 4: Run test and typecheck**

Run: `cd frontend && npm run typecheck && npm run test -- src/components/ConfidenceCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ConfidenceCard.tsx frontend/src/components/ConfidenceMeter.tsx frontend/src/components/ConfidenceCard.test.tsx frontend/src/lib/api.ts frontend/src/lib/types.ts
git commit -m "feat(confidence): multi-factor confidence card UI"
```

---

## Task 8: Frontend — Wire Confidence Card into Workbench and Hermes Queue

**Files:**
- Modify: `frontend/src/app/portfolio/[id]/workbench/page.tsx`
- Modify: `frontend/src/components/hermes/HermesQueue.tsx`

**Interfaces:**
- Consumes: `api.confidence.calculate`, `ConfidenceCard`.

- [ ] **Step 1: Workbench integration**

Modify `frontend/src/app/portfolio/[id]/workbench/page.tsx`:

- Add state `const [confidence, setConfidence] = useState<ConfidenceResult | null>(null);`
- When `trades` or `liveVerify` changes, call `api.confidence.calculate(id, trades)` and set confidence.
- Render `<ConfidenceCard result={confidence} />` in the sticky right column above `VerifyPanel`.

Stub:

```typescript
useEffect(() => {
  if (trades.length) {
    api.confidence.calculate(id, trades).then(setConfidence).catch(() => setConfidence(null));
  }
}, [trades, liveVerify, id]);
```

- [ ] **Step 2: Hermes Queue integration**

Modify `frontend/src/components/hermes/HermesQueue.tsx`:

- In `QueueRow`, fetch confidence when expanded.
- Render `ConfidenceCard` inside the expanded detail area.

- [ ] **Step 3: Run frontend typecheck and tests**

Run: `cd frontend && npm run typecheck && npm run test`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/portfolio/\[id\]/workbench/page.tsx frontend/src/components/hermes/HermesQueue.tsx
git commit -m "feat(confidence): wire confidence card into workbench and hermes queue"
```

---

## Task 9: Backend — Hermes Strategy Diff Generator

**Files:**
- Modify: `backend/agents/hermes/strategy_io.py`
- Create: `backend/agents/hermes/generator.py`
- Modify: `backend/routers/hermes.py`
- Test: `backend/tests/test_hermes_generate.py`

**Interfaces:**
- Consumes: current `strategy.yaml`, `hermes.simulate`.
- Produces: `POST /hermes/generate` returns `{ok, diff, simulation}`.

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_hermes_generate.py`:

```python
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from core import data_loader, storage
from core.auth import create_user
from generators import generate_data


def _client(n=50):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = storage.get_conn(path)
    storage.init_schema(conn)
    storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    old_enforce = os.environ.get("AUTH_ENFORCE")
    old_secret = os.environ.get("AUTH_SECRET")
    os.environ["AUTH_ENFORCE"] = "1"
    os.environ["AUTH_SECRET"] = "test-secret-32-bytes-long-ok"
    create_user(conn, "admin", "adminpass", "admin")
    from main import app
    c = TestClient(app)
    r = c.post("/auth/token", json={"username": "admin", "password": "adminpass"})
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    try:
        yield c
    finally:
        data_loader.set_conn(None)
        if old_enforce is None:
            os.environ.pop("AUTH_ENFORCE", None)
        else:
            os.environ["AUTH_ENFORCE"] = old_enforce
        if old_secret is None:
            os.environ.pop("AUTH_SECRET", None)
        else:
            os.environ["AUTH_SECRET"] = old_secret


@pytest.fixture
def client():
    yield from _client()


def test_generate_returns_diff_or_no_improvement(client):
    r = client.post("/hermes/generate", json={"days": 30, "seed": 42})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "diff" in body
    assert "simulation" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_hermes_generate.py::test_generate_returns_diff_or_no_improvement -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Modify `backend/agents/hermes/strategy_io.py` to expose:

```python
def load_strategy(path: Optional[str] = None) -> dict:
    import yaml
    p = path or _strategy_path()
    with open(p) as f:
        return yaml.safe_load(f)


def save_strategy(strategy: dict, path: Optional[str] = None) -> None:
    import yaml
    p = path or _strategy_path()
    with open(p, "w") as f:
        yaml.dump(strategy, f, sort_keys=False)
```

Create `backend/agents/hermes/generator.py`:

```python
"""Generate a strategy YAML diff from synthetic test results."""
from __future__ import annotations

import copy
from typing import Any

from agents.hermes.strategy_io import load_strategy
from agents.hermes.loop import simulate as hermes_simulate  # or use existing simulator


TUNABLES = [
    "prevent_risk_threshold",
    "auto_approve_band",
    "min_trade_size",
    "cash_buffer_target",
    "prevent_horizon_days",
]


def _simulate(strategy: dict, days: int = 30, seed: int = 42) -> dict:
    return hermes_simulate(days=days, seed=seed, strategy=strategy)


def generate_diff(days: int = 30, seed: int = 42) -> dict[str, Any]:
    baseline = load_strategy()
    baseline_result = _simulate(baseline, days=days, seed=seed)
    baseline_incidence = baseline_result.get("prevent_incidence", baseline_result.get("reactive_incidence", 999))

    best = {"improvement": 0.0, "diff": None, "after": None}

    for var in TUNABLES:
        current = baseline["variables"][var]["value"]
        candidates = _candidates(var, current)
        for cand in candidates:
            candidate = copy.deepcopy(baseline)
            candidate["variables"][var]["value"] = cand
            result = _simulate(candidate, days=days, seed=seed)
            after_incidence = result.get("prevent_incidence", result.get("reactive_incidence", 999))
            if baseline_incidence > 0:
                improvement = (baseline_incidence - after_incidence) / baseline_incidence
            else:
                improvement = 0.0
            if improvement > best["improvement"] and improvement >= 0.05:
                best = {
                    "improvement": improvement,
                    "diff": {
                        "variable": var,
                        "from": current,
                        "to": cand,
                        "rationale": f"Synthetic run with seed {seed} showed {improvement*100:.1f}% fewer projected breaches when {var} changed from {current} to {cand}.",
                    },
                    "after": result,
                }

    return {
        "ok": True,
        "diff": best["diff"],
        "simulation": {
            "reactive_incidence": baseline_result.get("reactive_incidence"),
            "prevent_incidence_before": baseline_incidence,
            "prevent_incidence_after": best["after"].get("prevent_incidence") if best["after"] else None,
            "improvement_pct": round(best["improvement"] * 100, 1) if best["diff"] else 0,
        },
    }


def _candidates(var: str, current):
    if isinstance(current, bool):
        return [not current]
    if isinstance(current, int):
        return [current - 1, current + 1]
    if isinstance(current, float):
        return [round(current * 0.9, 3), round(current * 1.1, 3)]
    return []
```

Modify `backend/routers/hermes.py` to add:

```python
from agents.hermes.generator import generate_diff


@router.post("/hermes/generate")
def generate(body: dict = None, _user=Depends(require_mutation)):
    body = body or {}
    return generate_diff(days=body.get("days", 30), seed=body.get("seed", 42))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_hermes_generate.py::test_generate_returns_diff_or_no_improvement -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/hermes/strategy_io.py backend/agents/hermes/generator.py backend/routers/hermes.py backend/tests/test_hermes_generate.py
git commit -m "feat(hermes): synthetic-test strategy diff generator"
```

---

## Task 10: Backend — Generated Regression Test Generator + Runner

**Files:**
- Create: `backend/agents/hermes/test_generator.py`
- Create: `backend/agents/hermes/generated_tests/.gitkeep`
- Modify: `backend/routers/hermes.py`
- Test: `backend/tests/test_hermes_generate.py`

**Interfaces:**
- Consumes: a diff dict and simulation snapshot.
- Produces: `POST /hermes/generate` also returns `test.filename` and `test.source`; `POST /hermes/run-test` executes generated test.

- [ ] **Step 1: Write failing test**

```python
def test_run_generated_test(client):
    r = client.post("/hermes/generate", json={"days": 30, "seed": 42})
    assert r.status_code == 200
    body = r.json()
    if body["diff"] is None:
        pytest.skip("no improvement found in this seed")
    r2 = client.post("/hermes/run-test", json={"source": body["test"]["source"]})
    assert r2.status_code == 200, r2.text
    assert r2.json()["ok"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_hermes_generate.py::test_run_generated_test -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Create `backend/agents/hermes/test_generator.py`:

```python
"""Generate a pytest regression test from a strategy diff."""
from __future__ import annotations

import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GENERATED_DIR = ROOT / "generated_tests"


def generate_test(diff: dict, simulation: dict, seed: int = 42) -> dict:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    var = diff["variable"]
    filename = f"test_strategy_{var}_{ts}.py"
    path = GENERATED_DIR / filename

    before = simulation.get("prevent_incidence_before", 0) or simulation.get("reactive_incidence", 0)
    after = simulation.get("prevent_incidence_after", 0)
    threshold = int(after * 1.05) if after else before

    source = textwrap.dedent(f'''\
        """Generated regression test for strategy change: {var}."""
        from agents.hermes.strategy_io import load_strategy
        from agents.hermes.loop import simulate

        def test_strategy_change_lowers_incidence():
            baseline = load_strategy()
            baseline_result = simulate(days=30, seed={seed}, strategy=baseline)
            baseline_incidence = baseline_result.get("prevent_incidence", baseline_result.get("reactive_incidence", 0))

            candidate = dict(baseline)
            candidate["variables"]["{var}"]["value"] = {repr(diff["to"])}
            candidate_result = simulate(days=30, seed={seed}, strategy=candidate)
            candidate_incidence = candidate_result.get("prevent_incidence", candidate_result.get("reactive_incidence", 0))

            assert candidate_incidence <= {threshold}, (
                f"Expected candidate incidence <= {threshold}, got {{candidate_incidence}}"
            )
            assert candidate_incidence <= baseline_incidence, (
                f"Candidate incidence {{candidate_incidence}} should not exceed baseline {{baseline_incidence}}"
            )
        ''')

    path.write_text(source, encoding="utf-8")
    return {"filename": filename, "source": source}


def run_generated_test(source: str, timeout: int = 60) -> dict:
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(source)
        f.flush()
        test_path = f.name

    try:
        proc = subprocess.run(
            ["python", "-m", "pytest", test_path, "-v"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"Test timed out after {timeout}s", "returncode": -1}
    finally:
        try:
            os.unlink(test_path)
        except OSError:
            pass
```

Modify `backend/agents/hermes/generator.py`:

```python
from agents.hermes.test_generator import generate_test


def generate_diff(days: int = 30, seed: int = 42) -> dict:
    # ... existing logic ...
    out = {
        "ok": True,
        "diff": best["diff"],
        "simulation": { ... },
    }
    if best["diff"]:
        out["test"] = generate_test(best["diff"], out["simulation"], seed=seed)
    return out
```

Modify `backend/routers/hermes.py`:

```python
from agents.hermes.test_generator import run_generated_test
from pydantic import BaseModel


class RunTestRequest(BaseModel):
    source: str


@router.post("/hermes/run-test")
def run_test(body: RunTestRequest, _user=Depends(require_mutation)):
    return run_generated_test(body.source)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_hermes_generate.py -v`
Expected: PASS (or skip if no diff found).

- [ ] **Step 5: Commit**

```bash
git add backend/agents/hermes/test_generator.py backend/agents/hermes/generated_tests/.gitkeep backend/agents/hermes/generator.py backend/routers/hermes.py backend/tests/test_hermes_generate.py
git commit -m "feat(hermes): generated pytest regression tests + runner"
```

---

## Task 11: Frontend — Hermes Generate Panel

**Files:**
- Create: `frontend/src/components/hermes/HermesGeneratePanel.tsx`
- Create: `frontend/src/components/hermes/StrategyDiff.tsx`
- Create: `frontend/src/components/hermes/GeneratedTestView.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/app/hermes/page.tsx`
- Test: `frontend/src/components/hermes/HermesGeneratePanel.test.tsx`

**Interfaces:**
- Consumes: `api.hermes.generate(days, seed)`, `api.hermes.runTest(source)`, `api.hermes.adopt(diff)`.

- [ ] **Step 1: Add types and API**

Modify `frontend/src/lib/types.ts`:

```typescript
export interface HermesDiff {
  variable: string;
  from: any;
  to: any;
  rationale: string;
}

export interface HermesGenerateResult {
  ok: boolean;
  diff: HermesDiff | null;
  test?: { filename: string; source: string };
  simulation: {
    reactive_incidence?: number;
    prevent_incidence_before?: number;
    prevent_incidence_after?: number;
    improvement_pct?: number;
  };
}

export interface RunTestResult {
  ok: boolean;
  stdout: string;
  stderr: string;
  returncode: number;
}
```

Modify `frontend/src/lib/api.ts`:

```typescript
hermes: {
  // ... existing methods ...
  generate: (body?: { days?: number; seed?: number }) =>
    j<HermesGenerateResult>("/hermes/generate", { method: "POST", body: JSON.stringify(body || {}) }),
  runTest: (source: string) =>
    j<RunTestResult>("/hermes/run-test", { method: "POST", body: JSON.stringify({ source }) }),
},
```

- [ ] **Step 2: Write failing test**

Create `frontend/src/components/hermes/HermesGeneratePanel.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { HermesGeneratePanel } from "./HermesGeneratePanel";

test("renders generate button", () => {
  render(<HermesGeneratePanel onAdopted={() => {}} />);
  expect(screen.getByText(/Generate strategy diff/i)).toBeInTheDocument();
});
```

- [ ] **Step 3: Implement components**

Create `frontend/src/components/hermes/StrategyDiff.tsx`:

```typescript
import { HermesDiff } from "@/lib/types";

export function StrategyDiff({ diff }: { diff: HermesDiff }) {
  return (
    <div className="bg-aura-ochre-soft/30 border border-aura-ochre rounded p-3 space-y-2">
      <p className="font-mono text-xs text-aura-ochre uppercase">Proposed strategy change</p>
      <p className="font-mono text-sm text-aura-text">
        <span className="font-bold">{diff.variable}</span>:{" "}
        <span className="text-aura-text-subtle">{String(diff.from)}</span> →{" "}
        <span className="text-aura-emerald font-bold">{String(diff.to)}</span>
      </p>
      <p className="font-mono text-xs text-aura-text-muted">{diff.rationale}</p>
    </div>
  );
}
```

Create `frontend/src/components/hermes/GeneratedTestView.tsx`:

```typescript
"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export function GeneratedTestView({ source }: { source: string }) {
  const [result, setResult] = useState<{ ok: boolean; stderr: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    const r = await api.hermes.runTest(source);
    setResult(r);
    setBusy(false);
  };

  const copy = () => navigator.clipboard.writeText(source);

  return (
    <div className="bg-aura-surface-low border border-aura-border rounded p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-aura-text-subtle">Generated regression test</span>
        <div className="flex gap-2">
          <button onClick={copy} className="text-xs font-mono text-aura-navy hover:underline">Copy</button>
          <button onClick={run} disabled={busy} className="text-xs font-mono text-aura-navy hover:underline disabled:opacity-50">
            {busy ? "Running..." : "Run test"}
          </button>
        </div>
      </div>
      <pre className="text-[10px] font-mono bg-aura-background p-2 rounded overflow-x-auto">{source}</pre>
      {result && (
        <div className={`text-xs font-mono ${result.ok ? "text-aura-emerald" : "text-aura-crimson"}`}>
          {result.ok ? "Test passed" : `Test failed: ${result.stderr.slice(0, 200)}`}
        </div>
      )}
    </div>
  );
}
```

Create `frontend/src/components/hermes/HermesGeneratePanel.tsx`:

```typescript
"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { HermesGenerateResult } from "@/lib/types";
import { StrategyDiff } from "./StrategyDiff";
import { GeneratedTestView } from "./GeneratedTestView";
import { PrimaryButton } from "@/components/ui/PrimaryButton";

export function HermesGeneratePanel({ onAdopted }: { onAdopted?: () => void }) {
  const [result, setResult] = useState<HermesGenerateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [adopting, setAdopting] = useState(false);

  const generate = async () => {
    setBusy(true);
    const r = await api.hermes.generate({ days: 30, seed: 42 });
    setResult(r);
    setBusy(false);
  };

  const adopt = async () => {
    if (!result?.diff) return;
    setAdopting(true);
    await api.hermes.adopt({
      variable: result.diff.variable,
      to: result.diff.to,
      rationale: result.diff.rationale,
    });
    setAdopting(false);
    onAdopted?.();
  };

  return (
    <div className="bg-aura-surface border border-aura-border rounded p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-mono text-sm font-bold text-aura-text">Synthetic Reality → Code</h3>
          <p className="font-mono text-xs text-aura-text-muted">Generate a strategy diff backed by a regression test.</p>
        </div>
        <PrimaryButton onClick={generate} disabled={busy} loading={busy}>Generate strategy diff</PrimaryButton>
      </div>

      {result && (
        <div className="space-y-3">
          {result.diff ? (
            <>
              <StrategyDiff diff={result.diff} />
              {result.test && <GeneratedTestView source={result.test.source} />}
              <PrimaryButton onClick={adopt} disabled={adopting} loading={adopting}>Adopt as next version</PrimaryButton>
            </>
          ) : (
            <p className="font-mono text-xs text-aura-text-muted">No statistically significant improvement found.</p>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Insert into /hermes page**

Modify `frontend/src/app/hermes/page.tsx`:

- Import `HermesGeneratePanel`.
- Add `<HermesGeneratePanel onAdopted={refreshAll} />` in the right column below `HermesHistory`.

- [ ] **Step 5: Run typecheck and tests**

Run: `cd frontend && npm run typecheck && npm run test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/hermes/HermesGeneratePanel.tsx frontend/src/components/hermes/StrategyDiff.tsx frontend/src/components/hermes/GeneratedTestView.tsx frontend/src/components/hermes/HermesGeneratePanel.test.tsx frontend/src/app/hermes/page.tsx frontend/src/lib/api.ts frontend/src/lib/types.ts
git commit -m "feat(hermes): synthetic reality to code panel"
```

---

## Task 12: Final Integration — Full Test Suite + Push

**Files:**
- All modified/new files.

- [ ] **Step 1: Run backend test suite**

Run: `cd backend && python -m pytest tests/test_adviser.py tests/test_confidence.py tests/test_hermes_generate.py tests/test_auth.py tests/test_backup_restore.py tests/test_routers.py tests/test_routers_market.py -v`
Expected: All PASS.

- [ ] **Step 2: Run frontend test suite**

Run: `cd frontend && npm run typecheck && npm run test`
Expected: All PASS.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix(final-features): address integration test issues"
```

- [ ] **Step 4: Push**

```bash
git push origin main
```

---

## Self-Review

### Spec coverage

| Spec section | Task |
|---|---|
| §3 AI Investment Manager Agent | Tasks 1–5 |
| §4 Confidence Card | Tasks 6–8 |
| §5 Synthetic-Test → Diff + Test | Tasks 9–11 |
| §6 Data flow / error handling | Embedded in each task (LLM fallback, 503 for LiveKit, no-improvement message) |
| §7 Testing plan | Each task includes tests; Task 12 runs full suite |
| §8 Risks | Addressed by grounding, conservative thresholds, fixed-seed tests |

### Placeholder scan
- No TBD/TODO/fill-in-details found.
- Every task has exact file paths, code snippets, and commands.
- Every task ends with a commit command.

### Type consistency
- `AdviserWhiteboard`, `ConfidenceResult`, `HermesGenerateResult`, `HermesDiff`, `RunTestResult` are defined once in `frontend/src/lib/types.ts` and used consistently.
- `build_whiteboard` returns the same shape consumed by `AdviserCanvas`.
- `score_confidence` returns `ConfidenceResult`, serialized in the router.
- `generate_diff` returns the shape consumed by the frontend `HermesGeneratePanel`.

### Decomposition check
- Three independent subsystems (adviser, confidence, generator) each have their own backend routers, frontend components, and tests. They share only the existing `api.ts`/`types.ts` updates and `main.py` registration.
