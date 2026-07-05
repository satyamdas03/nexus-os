# ASSURE 2.0 Pilot Onboarding Template

Use this template to onboard a single adviser or small advisory team to the ASSURE 2.0 pilot. All pilot data remains synthetic until a formal production readiness review is completed.

---

## Pre-pilot checklist

- [ ] Pilot scope is agreed: number of synthetic portfolios, test duration, success metrics.
- [ ] A pilot owner (adviser or compliance lead) is assigned.
- [ ] The team has read `docs/DEPLOYMENT.md` and chosen a deployment target.
- [ ] Docker Compose stack has been started locally and `scripts/smoke_docker.py` passes.
- [ ] The team understands the two-tier safety cage: mandate rules = LAW, strategy = JUDGMENT.

---

## Week 1 — Orientation

| Day | Activity | Owner | Evidence |
|---|---|---|---|
| 1 | Log in to the Command Centre, view the book summary. | Pilot owner | Screenshot of book summary |
| 2 | Drill into 3 red portfolios, read the explain narrative. | Pilot owner | Saved explain outputs |
| 3 | Use the Workbench to simulate a fix, then approve/reject. | Pilot owner | Audit entry in `audit.jsonl` |
| 4 | Generate an Evidence Pack for one portfolio. | Pilot owner | Downloaded pack |
| 5 | Review the SOC 2 checklist and flag any blocking gaps. | Compliance lead | Signed review note |

---

## Week 2 — Hermes Mission Control

| Day | Activity | Owner | Evidence |
|---|---|---|---|
| 1 | Run a reactive **Scan Book** and review the queue. | Pilot owner | Hermes heartbeat screenshot |
| 2 | Approve one batch of gate-green remediation trades. | Pilot owner with manager sign-off | Audit entries |
| 3 | Run **Hermes Reflection** and adopt or dismiss a strategy tweak. | Pilot owner | Strategy version bump in `strategy.yaml` |
| 4 | Run a **Prevent Scan** and review projected-risk meta. | Pilot owner | Queue rows with `mode=prevent` |
| 5 | Run the 100-day simulation and compare reactive vs. prevent incidence. | Pilot owner | Simulation result JSON |

---

## Week 3 — Scale and feedback

- [ ] Run a full 34k-portfolio scan and measure latency.
- [ ] Collect feedback on narrative clarity and false-positive rate.
- [ ] File issues for any UI/UX gaps or rule-engine edge cases.
- [ ] Decide whether to proceed to production readiness (move to managed DB, auth, RBAC).

---

## Exit criteria

| Metric | Target | Actual | Pass? |
|---|---|---|---|
| Reactive scan latency (34k) | < 60s | | |
| Hermes queue gate-pass rate | > 95% | | |
| Prevent simulation breach reduction | ≥ 50% | | |
| Evidence pack generation | < 5s | | |
| Pilot team satisfaction | ≥ 4/5 | | |

---

## Sign-off

- Pilot owner: ___________________ Date: __________
- Compliance lead: ___________________ Date: __________
- Engineering lead: ___________________ Date: __________
