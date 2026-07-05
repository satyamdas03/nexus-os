# ASSURE 2.0 SOC 2 Readiness Checklist

This checklist maps the current ASSURE 2.0 pilot to the AICPA Trust Services Criteria (TSC). All data is synthetic in the pilot, but the checklist is written as if preparing for a production rollout with real client data.

## Legend

- ✅ Implemented
- 🟡 Partial / pilot-only
- ❌ Gap — must be addressed before production

---

## CC6 — Logical and Physical Access Controls

| TSC | Control Objective | Current State | Evidence Location | Gap / Remediation |
|---|---|---|---|---|
| CC6.1 | Logical access security measures are implemented and maintained. | 🟡 | `backend/routers/admin.py` has `X-Admin-Secret` gate; no role-based access control. | Add RBAC and integrate with corporate IdP (OIDC/SAML). |
| CC6.2 | Access is authorized, modified, or removed based on roles. | ❌ | No user identity layer in the pilot. | Implement authentication and per-adviser authorization. |
| CC6.3 | Access is removed promptly on termination. | ❌ | No user provisioning system. | Integrate with HR/IdP offboarding hooks. |
| CC6.6 | Encryption protects confidential information in transit. | ✅ | nginx/ALB terminates TLS; `connect-src 'self'` CSP; backend/frontend use HTTPS in prod. | Configure TLS 1.3 and HSTS. |
| CC6.7 | Encryption protects data at rest. | 🟡 | SQLite file rests on Docker volume/host disk; no application-level encryption. | Use managed Postgres with encrypted storage; encrypt sensitive audit columns. |
| CC6.8 | Security incident detection and monitoring. | 🟡 | `audit.jsonl` logs actions; no alerting. | Ship audit logs to SIEM and set breach/watch alerts. |

---

## CC7 — System Operations

| TSC | Control Objective | Current State | Evidence Location | Gap / Remediation |
|---|---|---|---|---|
| CC7.1 | System monitoring detects anomalies. | 🟡 | Health endpoints `/health`, `/v1/health`; Docker healthchecks. | Add structured metrics (Prometheus/CloudWatch) and anomaly detection. |
| CC7.2 | System operations are tracked and evaluated. | 🟡 | `audit.jsonl`, `status_history`, `drift_events`. | Centralize logs; define retention and review cadence. |
| CC7.3 | System failures are identified, evaluated, and corrected. | 🟡 | Docker restart policies; backend exceptions surface per-item. | Add error tracking (Sentry) and on-call runbook. |
| CC7.4 | Processing integrity is maintained. | ✅ | Deterministic rules engine (`assure-kernel`) is immutable; trades verified before persistence. | Document change-control for rules engine releases. |
| CC7.5 | System changes are authorized, tested, and approved. | 🟡 | Git-based change control; `strategy.yaml` is versioned and reversible. | Require PR review + CI gating for production deploys. |

---

## CC8 — Change Management

| TSC | Control Objective | Current State | Evidence Location | Gap / Remediation |
|---|---|---|---|---|
| CC8.1 | Changes are authorized, designed, tested, and approved. | ✅ | Git history; `tests/` for backend and frontend; `pytest` CI gate. | Add branch protection and required checks. |
| CC8.2 | Unauthorized changes are prevented. | 🟡 | `strategy_io._guard()` blocks AI writes outside `strategy.yaml`; mandate rules are read-only. | Separate CI/CD permissions; signed container images. |

---

## CC2 — Communication and Information

| TSC | Control Objective | Current State | Evidence Location | Gap / Remediation |
|---|---|---|---|---|
| CC2.1 | System boundaries are communicated. | ✅ | `docs/DEPLOYMENT.md`; nginx CSP headers; `frontend/next.config.js` security headers. | Publish internal network architecture diagram. |
| CC2.2 | System changes are communicated. | 🟡 | Commit messages and release notes informal. | Adopt semantic versioning and a public changelog. |
| CC2.3 | System risks are communicated. | 🟡 | Risk documented in this checklist. | Establish a risk register and quarterly review. |

---

## A1 — Availability

| TSC | Control Objective | Current State | Evidence Location | Gap / Remediation |
|---|---|---|---|---|
| A1.1 | Controls support system availability. | 🟡 | Docker `restart: unless-stopped`; healthchecks. | Add load balancer, autoscaling, and multi-zone deploy. |
| A1.2 | Controls monitor system availability. | 🟡 | Health endpoints exist. | Add synthetic uptime checks and paging. |
| A1.3 | Recovery point objective is defined. | ❌ | No formal RPO/RTO. | Define and test backup/restore procedures. |

---

## P1 — Privacy

| TSC | Control Objective | Current State | Evidence Location | Gap / Remediation |
|---|---|---|---|---|
| P1.1 | Personal information is collected only as needed. | ✅ | All pilot data is synthetic; no PII. | For production, implement data-classification and minimization review. |
| P1.2 | Use of personal information is limited. | ✅ | Pilot uses no real client data. | Production data flow review and DPA with vendors. |
| P1.3 | Personal information is retained only as needed. | ✅ | Pilot data can be wiped with `docker compose down -v`. | Define production retention and deletion policies. |

---

## Summary

| Category | ✅ | 🟡 | ❌ |
|---|---|---|---|
| Access | 1 | 2 | 2 |
| Operations | 2 | 3 | 0 |
| Change Management | 2 | 1 | 0 |
| Communication | 2 | 2 | 0 |
| Availability | 0 | 2 | 1 |
| Privacy | 3 | 0 | 0 |
| **Total** | **10** | **10** | **3** |

**Blockers before production pilot with regulated data:**
1. Implement authentication and RBAC (CC6.2, CC6.3).
2. Define and test backup/restore RPO/RTO (A1.3).
3. Centralize audit logging and alerting (CC6.8, CC7.1).
