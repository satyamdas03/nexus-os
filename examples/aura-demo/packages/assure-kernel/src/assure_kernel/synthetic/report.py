"""Stress-test report builder for the ASSURE Synthetic Reality Engine.

Turns the raw output of an adversarial sweep into human-readable JSON and a
print-ready HTML report. The report is fully deterministic given the same
AdversaryResult: no LLM generation, no non-deterministic summaries.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from assure_kernel.synthetic.adversary import AdversaryResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _status_badge_class(status: str) -> str:
    if status == "green":
        return "status-green"
    if status == "orange":
        return "status-orange"
    if status == "red":
        return "status-red"
    return "status-neutral"


def _render_scenario_table(scenario_counts: dict[str, dict[str, int]], total_per_scenario: int) -> str:
    rows = []
    for scenario_id in sorted(scenario_counts):
        counts = scenario_counts[scenario_id]
        total = sum(counts.values())
        green = counts.get("green", 0)
        orange = counts.get("orange", 0)
        red = counts.get("red", 0)
        rows.append(
            f"<tr>"
            f"<td>{_html_escape(scenario_id)}</td>"
            f"<td>{green}</td>"
            f"<td>{orange}</td>"
            f"<td class=\"breach\">{red}</td>"
            f"<td>{_format_percent(red / total) if total else '—'}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _render_rule_table(rule_counts: dict[str, int]) -> str:
    total = sum(rule_counts.values())
    rows = []
    for rule, count in sorted(rule_counts.items(), key=lambda kv: kv[1], reverse=True):
        pct = count / total if total else 0.0
        rows.append(
            f"<tr>"
            f"<td>{_html_escape(rule)}</td>"
            f"<td class=\"breach\">{count}</td>"
            f"<td>{_format_percent(pct)}</td>"
            f"</tr>"
        )
    if not rows:
        return '<tr><td colspan="3">No breaches observed.</td></tr>'
    return "\n".join(rows)


def _render_observation_rows(observations: list[dict[str, Any]]) -> str:
    if not observations:
        return '<tr><td colspan="6">No observations recorded.</td></tr>'
    rows = []
    for obs in observations[:100]:  # HTML caps at 100 inline rows.
        current = obs.get("current")
        limit = obs.get("limit")
        current_str = _html_escape(str(current)) if current is not None else "—"
        limit_str = _html_escape(str(limit)) if limit is not None else "—"
        rows.append(
            f"<tr>"
            f"<td>{_html_escape(obs['client_id'])}</td>"
            f"<td>{_html_escape(obs['scenario_id'])}</td>"
            f"<td>{_html_escape(obs['rule'])}</td>"
            f"<td>{current_str}</td>"
            f"<td>{limit_str}</td>"
            f"<td>{_html_escape(obs.get('plain') or '—')}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _render_html_report(result: dict[str, Any], generated_at: str) -> str:
    status_counts = result["scenario_status_counts"]
    n_scenarios = len(status_counts)
    n_per_scenario = result["total"] // n_scenarios if n_scenarios else 0

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ASSURE Synthetic Stress Report</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #0F172A; margin: 0; padding: 0; line-height: 1.55; font-size: 13px; }}
    .container {{ max-width: 960px; margin: 0 auto; padding: 32px 24px 80px; background: #FFFFFF; min-height: 100vh; }}
    header {{ border-bottom: 2px solid #0F172A; padding: 24px 0 16px; margin-bottom: 24px; }}
    .logo {{ font-size: 12px; font-weight: 700; letter-spacing: 0.1em; margin-bottom: 8px; }}
    h1 {{ font-size: 24px; margin: 0 0 8px; font-weight: 700; }}
    .subtitle {{ color: #475569; font-size: 12px; margin-bottom: 16px; }}
    section {{ margin: 28px 0; page-break-inside: avoid; }}
    h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 0.08em; border-bottom: 1px solid #CBD5E1; padding-bottom: 6px; margin: 0 0 14px; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
    .summary-card {{ padding: 16px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 4px; text-align: center; }}
    .summary-value {{ font-size: 28px; font-weight: 700; }}
    .summary-label {{ color: #64748B; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; }}
    .status-green {{ color: #15803D; background: #DCFCE7; }}
    .status-orange {{ color: #B45309; background: #FEF3C7; }}
    .status-red {{ color: #B91C1C; background: #FEE2E2; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }}
    th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #E2E8F0; }}
    th {{ font-weight: 600; color: #475569; background: #F8FAFC; }}
    td.breach {{ font-weight: 700; color: #B91C1C; }}
    .control-statement {{ background: #F1F5F9; padding: 14px; border-left: 4px solid #0F172A; font-size: 12px; color: #334155; }}
    footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #CBD5E1; color: #64748B; font-size: 11px; display: flex; justify-content: space-between; }}
    .observations {{ max-height: 400px; overflow-y: auto; border: 1px solid #E2E8F0; border-radius: 4px; }}
    .observations th {{ position: sticky; top: 0; z-index: 1; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo">ASSURE SYNTHETIC REALITY ENGINE</div>
      <h1>Stress-Test Report</h1>
      <div class="subtitle">Deterministic adversarial sweep generated {_html_escape(generated_at[:19])} UTC</div>
    </header>

    <section>
      <h2>Summary</h2>
      <div class="summary-grid">
        <div class="summary-card"><div class="summary-value">{result['total']}</div><div class="summary-label">Portfolios tested</div></div>
        <div class="summary-card"><div class="summary-value status-green">{result['green']}</div><div class="summary-label">Green</div></div>
        <div class="summary-card"><div class="summary-value status-orange">{result['orange']}</div><div class="summary-label">Watch</div></div>
        <div class="summary-card"><div class="summary-value status-red">{result['red']}</div><div class="summary-label">Breach</div></div>
      </div>
      <p><strong>Breach rate:</strong> {_format_percent(result['red'] / result['total']) if result['total'] else '—'}</p>
    </section>

    <section>
      <h2>Scenario Breakdown</h2>
      <table>
        <thead><tr><th>Scenario</th><th>Green</th><th>Watch</th><th>Breach</th><th>Breach rate</th></tr></thead>
        <tbody>
          {_render_scenario_table(status_counts, n_per_scenario)}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Top Breached Rules</h2>
      <table>
        <thead><tr><th>Rule</th><th>Count</th><th>Share</th></tr></thead>
        <tbody>
          {_render_rule_table(result['rule_breach_counts'])}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Sample Breach Observations</h2>
      <div class="observations">
        <table>
          <thead><tr><th>Client</th><th>Scenario</th><th>Rule</th><th>Current</th><th>Limit</th><th>Plain</th></tr></thead>
          <tbody>
            {_render_observation_rows(result['breach_observations'])}
          </tbody>
        </table>
      </div>
      <p style="color:#64748B;font-size:11px;margin-top:8px;">
        Showing up to 100 observations. Full dataset available in JSON export.
      </p>
    </section>

    <section>
      <h2>Determinism &amp; Control Statement</h2>
      <div class="control-statement">
        This report is generated entirely from ASSURE's deterministic rules engine.
        No LLM participates in the verdicts or counts shown above.
        Any AI remediation agent must be measured against this ground truth:
        an agent claim that contradicts the engine is automatically flagged as a divergence.
      </div>
    </section>

    <footer>
      <div>ASSURE v0.1.0 &nbsp;|&nbsp; Synthetic Reality Engine</div>
      <div>Generated {_html_escape(generated_at[:19])} UTC</div>
    </footer>
  </div>
</body>
</html>"""


@dataclass
class StressReport:
    """A deterministic JSON + HTML stress-test report."""

    result: AdversaryResult
    generated_at: str = field(default_factory=_now)

    @property
    def json(self) -> dict[str, Any]:
        """Return the full report as a JSON-serializable dict."""
        payload = self.result.to_dict()
        payload["generated_at"] = self.generated_at
        payload["version"] = "0.1.0"
        payload["determinism_note"] = (
            "This report is derived entirely from the deterministic ASSURE rules engine. "
            "No LLM-generated text participates in the verdicts, counts, or observations."
        )
        return payload

    def to_html(self) -> str:
        """Return a print-ready HTML rendering of the report."""
        return _render_html_report(self.json, self.generated_at)

    def dumps(self) -> str:
        """Return the JSON report as a formatted string."""
        return json.dumps(self.json, indent=2)


def build_report(result: AdversaryResult) -> StressReport:
    """Convenience constructor for a StressReport."""
    return StressReport(result=result)
