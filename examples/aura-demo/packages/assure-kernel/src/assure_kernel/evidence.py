"""Evidence pack builder for the ASSURE kernel service.

The kernel service is stateless, so this module builds a regulator-reviewable
evidence pack entirely from the inputs provided by the caller:
portfolio, mandate, rules result, optional alignment history, and optional
remediation audit log. It returns both structured JSON and a print-ready HTML
rendering.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from assure_kernel import evaluate_portfolio, describe_mandate, parse_mandate

EVIDENCE_VERSION = "0.1.0"

SYNTHETIC_DISCLAIMER = "Generated from data supplied by the caller."

_CONTROL_STATEMENT = (
    "This evidence pack is assembled from ASSURE's deterministic rules engine, "
    "which is the single source of truth for mandate compliance. AI/LLM components "
    "in ASSURE are advisory only and may not override the rules engine. Every "
    "material remediation action must be human-approved and appended to an "
    "immutable audit trail. Mandate rules are immutable; only remediation "
    "strategy parameters are adjustable, and those adjustments must also be "
    "human-gated, versioned, and audited."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reference_id(client_id: str, day: int, generated_at: str) -> str:
    raw = f"{client_id}|{day}|{generated_at}|{EVIDENCE_VERSION}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12].upper()


def _format_rule_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "—"
    if isinstance(value, float):
        return f"{value * 100:.2f}%"
    return str(value)


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _status_badge_class(status: str) -> str:
    if status == "green":
        return "status-green"
    if status == "orange":
        return "status-orange"
    if status == "red":
        return "status-red"
    return "status-neutral"


def _status_label(status: str) -> str:
    if status == "green":
        return "ALIGNED"
    if status == "orange":
        return "ATTENTION"
    if status == "red":
        return "BREACH"
    return status.upper()


def _compose_deterministic_summary(rules_result: dict) -> str:
    """Compose a deterministic plain-English summary from rules_result facts only."""
    status = rules_result.get("status", "unknown")
    breaches = rules_result.get("breaches", [])
    watches = rules_result.get("watches", [])

    if status == "green":
        return (
            "This portfolio is fully aligned with its mandate as of the report timestamp. "
            "The deterministic rules engine found no breaches and no watches."
        )

    if status == "orange":
        watch_names = [w.get("rule", "") for w in watches]
        watch_text = ", ".join(watch_names) if watch_names else "one or more drift watches"
        return (
            f"This portfolio is currently under watch. The deterministic rules engine "
            f"flagged the following watch(es): {watch_text}. No mandate breaches are present."
        )

    breach_names = [b.get("rule", "") for b in breaches]
    breach_text = ", ".join(breach_names) if breach_names else "one or more mandate breaches"
    return (
        f"This portfolio is currently in BREACH. The deterministic rules engine "
        f"flagged the following rule(s): {breach_text}. Human-approved remediation is required."
    )


def _render_html(evidence: dict) -> str:
    """Render a complete, standalone, print-ready HTML document."""
    h = evidence["header"]
    att = evidence["current_attestation"]
    summary = evidence["deterministic_summary"]
    history = evidence["alignment_history"]
    remediation = evidence["remediation_evidence"]
    mandate_doc = evidence["mandate_documentation"]

    rule_rows = []
    for row in att["per_rule"]:
        rule = _html_escape(row["rule"])
        current = _html_escape(_format_rule_value(row.get("current")))
        limit = _html_escape(_format_rule_value(row.get("limit")))
        passed = "PASS" if row.get("pass") else "FAIL"
        row_class = "rule-pass" if row.get("pass") else "rule-fail"
        rule_rows.append(
            f'<tr class="{row_class}"><td>{rule}</td><td>{current}</td><td>{limit}</td>'
            f'<td class="passfail">{passed}</td></tr>'
        )
    rules_table = "\n".join(rule_rows)

    hist_rows = []
    for row in history:
        status_class = _status_badge_class(row["status"])
        status_lbl = _status_label(row["status"])
        hist_rows.append(
            f'<tr><td class="day">Day {row["day"]}</td>'
            f'<td><span class="badge {status_class}">{status_lbl}</span></td>'
            f'<td>{row["breach_count"]}</td><td>{row["watch_count"]}</td></tr>'
        )
    history_table = "\n".join(hist_rows) if hist_rows else '<tr><td colspan="4">No historical status records provided.</td></tr>'

    strip_blocks = []
    for row in history:
        strip_blocks.append(
            f'<div class="strip-block {_status_badge_class(row["status"])}" '
            f'title="Day {row["day"]}: {row["status"]}"></div>'
        )
    status_strip = "\n".join(strip_blocks) if strip_blocks else '<p class="muted">No timeline data.</p>'

    rem_rows = []
    for entry in remediation:
        ts = _html_escape(entry.get("timestamp", "")[:19])
        actor = _html_escape(entry.get("actor", ""))
        action = _html_escape(entry.get("action_type", ""))
        tier = _html_escape(entry.get("tier", ""))
        payload = _html_escape(entry.get("payload_summary", ""))
        rationale = _html_escape(entry.get("rationale", ""))
        rules_status = entry.get("rules_status")
        status_cell = ""
        if rules_status:
            status_cell = f'<span class="badge {_status_badge_class(rules_status)}">{_status_label(rules_status)}</span>'
        rem_rows.append(
            f'<tr><td>{ts}</td><td>{actor}</td><td>{action}</td><td>{tier}</td>'
            f'<td>{payload}</td><td>{rationale}</td><td>{status_cell}</td></tr>'
        )
    remediation_table = "\n".join(rem_rows) if rem_rows else '<tr><td colspan="7">No remediation activity provided.</td></tr>'

    status_class = _status_badge_class(att["status"])
    status_label = _status_label(att["status"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASSURE Evidence Pack — {_html_escape(h["client_name"])} ({_html_escape(h["client_id"] )})</title>
<style>
  @page {{ margin: 18mm; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    background: #F1F5F9;
    color: #0F172A;
    margin: 0;
    padding: 0;
    line-height: 1.55;
    font-size: 13px;
  }}
  .container {{
    max-width: 900px;
    margin: 0 auto;
    padding: 32px 24px 80px;
    background: #FFFFFF;
    min-height: 100vh;
  }}
  header {{
    border-bottom: 2px solid #0F172A;
    padding: 24px 0 16px;
    margin-bottom: 24px;
  }}
  .logo {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.1em;
    color: #0F172A;
    margin-bottom: 8px;
  }}
  h1 {{
    font-size: 22px;
    margin: 0 0 8px;
    font-weight: 700;
  }}
  .subtitle {{
    color: #475569;
    font-size: 12px;
    margin-bottom: 16px;
  }}
  .meta-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px 24px;
    margin-top: 12px;
  }}
  .meta-row {{
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid #E2E8F0;
    padding: 4px 0;
  }}
  .meta-label {{ color: #64748B; }}
  .meta-value {{ font-weight: 600; text-align: right; }}
  section {{
    margin: 28px 0;
    page-break-inside: avoid;
  }}
  h2 {{
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border-bottom: 1px solid #CBD5E1;
    padding-bottom: 6px;
    margin: 0 0 14px;
  }}
  .status-card {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 4px;
    margin-bottom: 16px;
  }}
  .badge {{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }}
  .status-green, .rule-pass .passfail {{ background: #D1FAE5; color: #065F46; }}
  .status-orange {{ background: #FEF3C7; color: #92400E; }}
  .status-red, .rule-fail .passfail {{ background: #FEE2E2; color: #991B1B; }}
  .status-neutral {{ background: #F1F5F9; color: #334155; }}
  .summary-box {{
    background: #F1F5F9;
    border-left: 4px solid #0F172A;
    padding: 14px 16px;
    font-size: 13px;
    margin-bottom: 16px;
  }}
  .summary-label {{
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #64748B;
    margin-bottom: 6px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-top: 8px;
  }}
  th, td {{
    text-align: left;
    padding: 8px 10px;
    border-bottom: 1px solid #E2E8F0;
  }}
  th {{
    background: #F8FAFC;
    font-weight: 700;
    text-transform: uppercase;
    font-size: 10px;
    letter-spacing: 0.06em;
    color: #64748B;
  }}
  tr {{ page-break-inside: avoid; }}
  .passfail {{ font-weight: 700; }}
  .strip {{
    display: flex;
    gap: 2px;
    height: 22px;
    margin: 12px 0;
    border: 1px solid #CBD5E1;
    padding: 2px;
    border-radius: 4px;
  }}
  .strip-block {{
    flex: 1;
    min-width: 8px;
    border-radius: 2px;
  }}
  .control-statement {{
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 4px;
    padding: 16px;
    font-size: 12px;
    color: #334155;
  }}
  footer {{
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #CBD5E1;
    font-size: 11px;
    color: #64748B;
    display: flex;
    justify-content: space-between;
  }}
  .muted {{ color: #64748B; font-style: italic; }}
  .print-button {{
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: #0F172A;
    color: #FFFFFF;
    border: none;
    padding: 12px 20px;
    border-radius: 4px;
    font-family: inherit;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.2);
  }}
  .print-button:hover {{ background: #334155; }}
  @media print {{
    body {{ background: #FFFFFF; color: #000000; }}
    .container {{ padding: 0; max-width: 100%; }}
    .print-button {{ display: none; }}
    .badge {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .status-card, .summary-box, .control-statement {{ background: #F8FAFC !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    section {{ page-break-inside: avoid; }}
    table {{ page-break-inside: auto; }}
    tr {{ page-break-inside: avoid; }}
  }}
</style>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo">ASSURE / PORTFOLIO ASSURANCE</div>
      <h1>Evidence Pack — {_html_escape(h["client_name"])}</h1>
      <div class="subtitle">Client ID: {_html_escape(h["client_id"])} &nbsp;|&nbsp; Adviser: {_html_escape(h["adviser"])}</div>
      <div class="meta-grid">
        <div class="meta-row"><span class="meta-label">Total FUM</span><span class="meta-value">${_html_escape(f"{h['fum']:,.2f}")}</span></div>
        <div class="meta-row"><span class="meta-label">Report Day</span><span class="meta-value">{_html_escape(str(h['day']))}</span></div>
        <div class="meta-row"><span class="meta-label">Generated</span><span class="meta-value">{_html_escape(h['generated_at'][:19])}</span></div>
        <div class="meta-row"><span class="meta-label">Reference ID</span><span class="meta-value">{_html_escape(h['reference_id'])}</span></div>
      </div>
    </header>

    <section>
      <h2>Current Compliance Attestation</h2>
      <div class="status-card">
        <span class="badge {status_class}">{status_label}</span>
        <span>Deterministic rules-engine result as of report generation.</span>
      </div>
      <table>
        <thead>
          <tr><th>Rule</th><th>Current</th><th>Limit / Target</th><th>Result</th></tr>
        </thead>
        <tbody>
          {rules_table}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Deterministic Summary</h2>
      <div class="summary-box">
        <div class="summary-label">Generated from rules-engine result — advisory-free</div>
        {_html_escape(summary)}
      </div>
    </section>

    <section>
      <h2>Mandate Rules</h2>
      <table>
        <thead>
          <tr><th>Rule</th><th>Type</th><th>Severity</th><th>Description</th></tr>
        </thead>
        <tbody>
          {_mandate_rows(mandate_doc)}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Alignment History</h2>
      <div class="strip">
        {status_strip}
      </div>
      <table>
        <thead>
          <tr><th>Day</th><th>Status</th><th>Breaches</th><th>Watches</th></tr>
        </thead>
        <tbody>
          {history_table}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Remediation Evidence</h2>
      <table>
        <thead>
          <tr><th>Timestamp</th><th>Actor</th><th>Action</th><th>Tier</th><th>Details</th><th>Rationale</th><th>Result</th></tr>
        </thead>
        <tbody>
          {remediation_table}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Determinism &amp; Control Statement</h2>
      <div class="control-statement">
        {_html_escape(_CONTROL_STATEMENT)}
      </div>
    </section>

    <footer>
      <div>
        Generated {_html_escape(h['generated_at'][:19])} UTC &nbsp;|&nbsp; Ref: {_html_escape(h['reference_id'])}<br>
        {_html_escape(SYNTHETIC_DISCLAIMER)}
      </div>
      <div>ASSURE v{EVIDENCE_VERSION}</div>
    </footer>
  </div>
  <button class="print-button" onclick="window.print()">Print / Save as PDF</button>
</body>
</html>"""


def _mandate_rows(mandate_doc: dict) -> str:
    rows = []
    for rule in mandate_doc.get("rules", []):
        title = _html_escape(rule.get("title", ""))
        rule_type = _html_escape(rule.get("type", ""))
        severity = _html_escape(rule.get("severity") or "—")
        description = _html_escape(rule.get("description", ""))
        rows.append(
            f"<tr><td>{title}</td><td>{rule_type}</td><td>{severity}</td><td>{description}</td></tr>"
        )
    if not rows:
        return '<tr><td colspan="4">No mandate rules provided.</td></tr>'
    return "\n".join(rows)


def build_evidence(
    portfolio: dict,
    mandate: dict,
    client_name: str | None = None,
    adviser: str | None = None,
    fum: float | None = None,
    day: int = 0,
    alignment_history: list[dict] | None = None,
    remediation_evidence: list[dict] | None = None,
) -> dict:
    """Assemble a stateless evidence pack from caller-supplied inputs.

    The rules result is computed fresh inside this function so the pack always
    reflects the deterministic verdict for the supplied portfolio + mandate.
    """
    parsed_mandate = parse_mandate(mandate) if isinstance(mandate, dict) else mandate
    result = evaluate_portfolio(portfolio, parsed_mandate)
    result_legacy = result.to_legacy()

    generated_at = _now()
    ref_id = _reference_id(portfolio.get("client_id", "unknown"), day, generated_at)

    header = {
        "client_name": client_name or portfolio.get("client_name") or "Unnamed Client",
        "client_id": portfolio.get("client_id", "unknown"),
        "adviser": adviser or portfolio.get("adviser") or "—",
        "fum": fum if fum is not None else portfolio.get("fum", 0.0),
        "day": day,
        "generated_at": generated_at,
        "reference_id": ref_id,
        "synthetic_data": False,
        "synthetic_disclaimer": SYNTHETIC_DISCLAIMER,
    }

    current_attestation = {
        "status": result_legacy["status"],
        "per_rule": [
            {
                "rule": r["rule"],
                "current": r.get("current"),
                "limit": r.get("limit"),
                "pass": bool(r.get("pass")),
                "severity": r.get("severity", "green"),
            }
            for r in result_legacy.get("per_rule", [])
        ],
    }

    mandate_doc = describe_mandate(parse_mandate(mandate))

    evidence = {
        "version": EVIDENCE_VERSION,
        "header": header,
        "current_attestation": current_attestation,
        "deterministic_summary": _compose_deterministic_summary(result_legacy),
        "mandate_documentation": mandate_doc,
        "alignment_history": alignment_history or [],
        "remediation_evidence": remediation_evidence or [],
        "control_statement": _CONTROL_STATEMENT,
        "footer": {
            "generated_at": generated_at,
            "reference_id": ref_id,
            "synthetic_disclaimer": SYNTHETIC_DISCLAIMER,
        },
    }

    evidence["_html"] = _render_html(evidence)
    return evidence
