# AURA Demo — Deploy Fix & Hardening Design

**Date:** 2026-06-18
**Status:** Approved
**Goal:** Make `aura-demo` (https://aura-demo-rho.vercel.app) fully live end-to-end: home, diagnosis, workbench all functional. Eliminate the env-bake fragility that caused client pages to hang on LOADING.

## Problem

Two Vercel projects point at the same GitHub repo `satyamdas03/aura-demo`:
- `aura-demo` — has Production deployment (canonical).
- `prototyping` — no Production deployment (stray duplicate).

`aura-demo` is broken on dynamic routes:
- `/` renders (home is a server component, reads env at runtime). ✓
- `/portfolio/c000` stuck on `LOADING`. ✗
- `/portfolio/c000/workbench` stuck on `LOADING`. ✗

### Root cause

`frontend/src/lib/api.ts` `base()`:
```js
const configured = process.env.NEXT_PUBLIC_API_URL;        // baked at BUILD time
if (configured && configured.startsWith("http")) return configured;
if (typeof window === "undefined") return "http://127.0.0.1:8000";
return "/api";   // browser fallback
```

Diagnosis + Workbench are `"use client"` → fetch in browser. `NEXT_PUBLIC_*` vars are inlined into the client bundle **at build time**. If the env var is empty/missing at build, `configured` is undefined → browser hits `/api` → but `next.config.js` rewrites `/api`→backend are **dev-only** (`NODE_ENV === "development"`). Prod has no `/api` proxy → `/api/portfolio/c000` → 404 → infinite LOADING.

Backend itself is healthy: `https://aura-backend-1igf.onrender.com/health` → `{"status":"ok"}`, CORS `allow_origins=["*"]`.

Previous session memory misdiagnosed this as "Root Directory wrongly set to `frontend`; change to `.`". That is **wrong** — the Next.js app genuinely lives in `frontend/` (package.json, src/, next.config.js, vercel.json all there; no root package.json). Root Directory `frontend` is correct.

## Design

Switch from "client knows backend URL via baked public env" to "same-origin server proxy". Client never knows the backend URL; all requests go through Next's rewrite proxy which is configured from a **server-only** env var. Removes build-time baking dependency entirely.

### 1. `frontend/next.config.js`

Rewrites always proxy `/api/:path*` → `${API_URL}/:path*` (dev and prod alike). `API_URL` is a non-public, server-only env var (read by next.config at build/runtime, never shipped to client).

```js
const backend = process.env.API_URL || "http://localhost:8000";
module.exports = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
  },
};
```

### 2. `frontend/src/lib/api.ts` `base()`

- Client (browser): return `/api` (same-origin; rewrite proxy handles routing). Never depends on baked env.
- Server (RSC on Vercel, e.g. home): return absolute `API_URL` (server-only env) with localhost fallback for dev. Server-side fetch needs absolute URL.

Drop `NEXT_PUBLIC_API_URL` dependency. Remove it from Vercel env (or leave harmlessly unused — prefer remove to avoid confusion).

### 3. Error UX — visible failure instead of silent hang

`frontend/src/app/portfolio/[id]/page.tsx` and `.../workbench/page.tsx`: catch fetch rejection, set an error state. Render `> BACKEND_UNREACHABLE // retry` instead of infinite `LOADING`. Future outages become visible, not a mystery hang.

### 4. Vercel project reconciliation

- Set `API_URL=https://aura-backend-1igf.onrender.com` on `aura-demo` Production (server-only, non-public).
- Remove `NEXT_PUBLIC_API_URL` from `aura-demo` (no longer used).
- **Delete** the `prototyping` Vercel project (stray duplicate, no production deployment).
- Keep Root Directory `frontend` (correct).

### 5. Rebuild

Clean Production redeploy on `aura-demo` with "use existing Build Cache" **unchecked**, so new code + `API_URL` are live.

### 6. Verification

- `curl /` → title + NEO_FINANCE
- `curl /portfolio/c000` → Bluecrest / BREACH / HOLDINGS_LEDGER (no LOADING)
- `curl /portfolio/c000/workbench` → PORTFOLIO_DELTA_SYNC / PROPOSED_EXECUTION_LEDGER
- Browser smoke: propose → verify → approve → audit trail populates

## End state

- Single canonical Vercel project `aura-demo`, 3 live functional routes.
- No build-time env baking dependency — client uses same-origin proxy; backend URL lives only in server env.
- Failures visible (error state, not silent hang).
- Stale memory corrected.

## Out of scope

- Backend changes (already healthy, CORS open).
- UI/feature work beyond the error-state addition.
- Real `ANTHROPIC_API_KEY` wiring (demo runs MockLLM offline; separate concern).