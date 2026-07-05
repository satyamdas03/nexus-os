# Workbench Assurance Check Stale-State Fix — Design

## Problem

In the **Remediation Workbench**, after a user clicks **Approve & Log**, the backend records the trades and returns a fresh `rules_result`. The page correctly updates:

- the `StatusBadge` to green/aligned
- the `newStatus` confirmation banner
- `p.rules_result`

But the **Assurance Check** sidebar (the `VerifyPanel` component) remains stale because it reads from `res?.verification` — the *pre-approval* remediation result that generated the proposed trades. It does not reflect the post-approval deterministic rules check.

## Root Cause

`workbench/page.tsx` computes:

```ts
const verifyResult = liveVerify ?? res?.verification ?? null;
const resolved = liveVerify ? liveVerify.status === "green" : res?.resolved ?? false;
```

After approval, `res` and `liveVerify` are not refreshed. The `VerifyPanel` therefore still renders the old breach/compliant split.

## Chosen Approach: B — Use approve response rules_result directly

Add a new state slice `approvedRulesResult`. When `api.approve()` succeeds, set it from `r.rules_result`. Then prefer it in the `verifyResult` / `resolved` derivation:

```ts
const verifyResult = liveVerify ?? approvedRulesResult ?? res?.verification ?? null;
const resolved = verifyResult ? verifyResult.status === "green" : res?.resolved ?? false;
```

### Why B

- **No extra backend calls** — works on Render free tier without waiting for LLM twice.
- **Minimal change** — single file, no API changes, no data model changes.
- **Preserves UI** — the proposed trade list and audit trail remain visible after approval.

### Tiny regressions to check while in the file

1. The green confirmation banner (`approved && newStatus`) must still appear.
2. `p.rules_result` must still be patched so the page header `StatusBadge` flips green.
3. `confidenceLabel` should continue to derive from `verifyResult` after approval.
4. Ensure `VerifyPanel` is not rendered with `verification={verifyResult}` when `verifyResult` is still null (currently it is only rendered when non-null).

## Files to Touch

- `frontend/src/app/portfolio/[id]/workbench/page.tsx`

## Implementation Details

1. Add state:
   ```ts
   const [approvedRulesResult, setApprovedRulesResult] = useState<RulesResult | null>(null);
   ```

2. In `approve()`:
   ```ts
   api.approve(id, {...}).then((r) => {
     setApproved(true);
     setNewStatus(r?.new_status ?? null);
     if (r?.rules_result) {
       setApprovedRulesResult(r.rules_result);
       setP((prev) => prev ? { ...prev, rules_result: r.rules_result } : prev);
     }
   });
   ```

3. Update derivation:
   ```ts
   const verifyResult = liveVerify ?? approvedRulesResult ?? res?.verification ?? null;
   const resolved = verifyResult ? verifyResult.status === "green" : res?.resolved ?? false;
   const perRule = verifyResult?.per_rule ?? res?.verification?.per_rule ?? [];
   const rulesPass = perRule.filter((r) => r.pass).length;
   const rulesTotal = perRule.length;
   ```

4. Reset `approvedRulesResult` when `id` changes or the user resets/proposes again, so previous approvals don't leak into a new portfolio view.

## Testing

1. Open a breached portfolio workbench.
2. Click **Propose a fix**.
3. Click **Approve & Log**.
4. Assert:
   - Banner: `APPROVED // trades logged`.
   - Status badge: green/aligned.
   - Assurance Check sidebar: **COMPLIANT** + all per-rule checkmarks green.
5. Navigate to another portfolio and back; no stale approved state should carry over.

## Out of Scope

- No backend changes.
- No API contract changes.
- No design system changes.
