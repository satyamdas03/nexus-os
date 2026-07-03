# Workbench Assurance Check Stale-State Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Remediation Workbench Assurance Check sidebar reflect the post-approval rules result immediately after a user clicks **Approve & Log**.

**Architecture:** Add an `approvedRulesResult` state slice to the Workbench page. After `api.approve()` succeeds, store `r.rules_result`. Derive `verifyResult` and `resolved` by preferring this fresh result, then fall back to `liveVerify` and the original `res?.verification`. No backend or API changes.

**Tech Stack:** React 18, TypeScript, Next.js App Router, Tailwind CSS, project-specific `api` client and types.

## Global Constraints

- No new runtime dependencies.
- No backend or API contract changes.
- Preserve the green approval banner, header `StatusBadge`, and audit trail behavior.
- Reset stale approval state when the portfolio `id` changes.

---

## File Map

- **Modify:** `frontend/src/app/portfolio/[id]/workbench/page.tsx`
  - Responsibility: Workbench UI state, proposal/approval flow, and rendering of `VerifyPanel`.
- **No new files.**

---

### Task 1: Add approved-rules-result state and update approval handler

**Files:**
- Modify: `frontend/src/app/portfolio/[id]/workbench/page.tsx:18-23`
- Modify: `frontend/src/app/portfolio/[id]/workbench/page.tsx:50-61`
- Modify: `frontend/src/app/portfolio/[id]/workbench/page.tsx:25-27`

**Interfaces:**
- Consumes: `RulesResult` from `@/lib/types`, `api.approve()` returns `ApproveResult` with `rules_result: RulesResult`.
- Produces: `approvedRulesResult` state; `setApprovedRulesResult` setter; `setP` updater uses functional form.

- [ ] **Step 1: Add state slice after existing `useState` declarations**

At line ~18 (after `const [resetting, setResetting] = useState(false);`), add:

```typescript
const [approvedRulesResult, setApprovedRulesResult] = useState<RulesResult | null>(null);
```

- [ ] **Step 2: Clear approved result when portfolio id changes**

Inside the existing `useEffect` that fetches the portfolio, add a reset so the prior portfolio's approval state never leaks:

```typescript
useEffect(() => {
  setApprovedRulesResult(null);
  api.getPortfolio(id).then(setP).catch(() => setErr(true));
}, [id]);
```

- [ ] **Step 3: Update approve handler to capture and store post-approval rules result**

Replace lines 50–61 with:

```typescript
const approve = () => {
  api.approve(id, {
    trades,
    rationale: res?.resolved && !liveVerify ? "approved AI proposal" : "approved with manual edits",
    breach_type: p.rules_result!.breaches[0]?.rule,
    choice: trades[0] ? `${trades[0].action} ${trades[0].ticker}` : "manual",
  }).then((r) => {
    setApproved(true);
    setNewStatus(r?.new_status ?? null);
    if (r?.rules_result) {
      setApprovedRulesResult(r.rules_result);
      setP((prev) => (prev ? { ...prev, rules_result: r.rules_result } : prev));
    }
  });
};
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/portfolio/[id]/workbench/page.tsx
git commit -m "feat(workbench): capture post-approval rules result state"
```

---

### Task 2: Prefer approved rules result in VerifyPanel derivation

**Files:**
- Modify: `frontend/src/app/portfolio/[id]/workbench/page.tsx:63-78`

**Interfaces:**
- Consumes: `approvedRulesResult` from Task 1, existing `liveVerify`, `res`, `p`.
- Produces: `verifyResult`, `resolved`, `confidenceLabel` now reflect the latest authoritative rules check.

- [ ] **Step 1: Update derived values**

Replace lines 63–78 with:

```typescript
const aumImpact = trades.reduce((s, t) => s + Math.abs(t.value), 0) || 0;
const verifyResult = liveVerify ?? approvedRulesResult ?? res?.verification ?? null;
const resolved = verifyResult ? verifyResult.status === "green" : res?.resolved ?? false;

// Confidence is NOT a fake percentage. RemediationResult has no confidence
// field, so we derive an honest signal from the deterministic rules engine:
// how many of the per-rule checks pass after remediation. The rules engine -
// not the AI - decides compliance, so this is the truthful signal.
const perRule = verifyResult?.per_rule ?? res?.verification?.per_rule ?? [];
const rulesPass = perRule.filter((r) => r.pass).length;
const rulesTotal = perRule.length;
const confidenceLabel = verifyResult
  ? rulesTotal
    ? `Rules: ${rulesPass}/${rulesTotal} pass${res?.retried ? " - retried" : ""}`
    : `Verified by rules engine${res?.retried ? " - retried" : ""}`
  : null;
```

- [ ] **Step 2: Verify VerifyPanel receives non-null verification**

Confirm the existing conditional at lines 164–174 remains:

```tsx
{verifyResult ? (
  <VerifyPanel
    verification={verifyResult}
    resolved={resolved}
    retried={res?.retried ?? false}
  />
) : (
  ...
)}
```

No change needed; the non-null `verifyResult` guarantees `VerifyPanel` props are valid.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/portfolio/[id]/workbench/page.tsx
git commit -m "feat(workbench): use post-approval rules result in VerifyPanel"
```

---

### Task 3: Type-check, build, and local regression test

**Files:**
- No file changes.

- [ ] **Step 1: Run TypeScript type check**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 2: Run Next.js production build**

```bash
npm run build
```

Expected: build succeeds with no errors.

- [ ] **Step 3: Run backend tests to ensure no regressions**

```bash
cd ../backend
python -m pytest tests/ -q
```

Expected: 138 passed.

- [ ] **Step 4: Commit if all green**

If all checks pass, there is no code change beyond Tasks 1–2, so simply note the verified state. No commit required unless fixes emerged.

---

### Task 4: Deploy and verify on live Vercel/Render

**Files:**
- No file changes.

- [ ] **Step 1: Push to origin/main**

```bash
git push origin main
```

- [ ] **Step 2: Wait for Vercel deploy**

Open `https://aura-demo-rho.vercel.app/` and confirm no build errors.

- [ ] **Step 3: Verify the fix live**

1. Navigate to a breached portfolio and enter its workbench.
2. Click **Propose a fix**.
3. Click **Approve & Log**.
4. Assert:
   - Banner shows `APPROVED + LOGGED`.
   - Header `StatusBadge` flips to green/aligned.
   - Assurance Check sidebar shows **COMPLIANT** and every per-rule row has a green checkmark.
5. Navigate to another breached portfolio and back into its workbench; the Assurance Check panel must not show the previous portfolio's green state.

- [ ] **Step 4: Commit verification results or log findings**

If live verification passes, mark the task complete. If it fails, capture the new state and return to Task 2.

---

## Spec Coverage Check

| Spec Requirement | Task |
|---|---|
| Add `approvedRulesResult` state | Task 1 |
| Patch `p.rules_result` on approval | Task 1 |
| Prefer post-approval result in `verifyResult` / `resolved` | Task 2 |
| Keep confidence label derived from latest result | Task 2 |
| Reset stale state on `id` change | Task 1 |
| Preserve banner + badge behavior | Tasks 1–2 (no destructive changes) |
| Type check / build / backend tests | Task 3 |
| Live deploy verification | Task 4 |

## Placeholder Scan

No TBD, TODO, "implement later", or vague instructions. Every step shows exact code or exact commands.
