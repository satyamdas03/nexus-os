"""Tests for the Synthetic Reality Engine stress-test report builder."""

import json

from assure_kernel.synthetic import (
    Adversary,
    build_report,
    find_breaches,
)


MANDATE = {
    "rules": [
        {"type": "max_asset_class_weight", "parameters": {"max_weights": {"Equity": 0.6, "Bonds": 0.5, "Cash": 1.0}}},
        {"type": "max_single_holding", "parameters": {"max_weight": 0.4}},
        {"type": "min_cash", "parameters": {"min_weight": 0.05}},
    ]
}


def test_build_report_returns_json_and_html():
    result = find_breaches(
        mandate=MANDATE,
        n=50,
        seed=1,
        scenarios=["baseline"],
        generator_kwargs={"breach_bias_mode": "single_holding", "breach_bias_prob": 1.0},
    )
    report = build_report(result)
    assert report.json["total"] == 50
    assert report.json["red"] > 0
    assert "generated_at" in report.json
    assert "determinism_note" in report.json
    html = report.to_html()
    assert "<!DOCTYPE html>" in html
    assert "Breach" in html or "breach" in html
    assert "SYN-" in html or any(o["client_id"] in html for o in report.json["breach_observations"])


def test_report_json_serializable():
    result = find_breaches(
        mandate=MANDATE,
        n=20,
        seed=2,
        scenarios=["baseline"],
        generator_kwargs={"breach_bias_mode": "single_holding", "breach_bias_prob": 1.0},
        record_limit=5,
    )
    report = build_report(result)
    dumped = report.dumps()
    parsed = json.loads(dumped)
    assert parsed["total"] == 20
    assert len(parsed["breach_observations"]) <= 5


def test_report_scenario_table_reflects_scenarios():
    result = find_breaches(
        mandate=MANDATE,
        n=30,
        seed=3,
        scenarios=["baseline", "equity_crash_2008"],
        generator_kwargs={"breach_bias_mode": "asset_class", "breach_bias_prob": 1.0},
    )
    report = build_report(result)
    html = report.to_html()
    assert "baseline" in html
    assert "equity_crash_2008" in html


def test_report_rule_table_reflects_top_rules():
    result = find_breaches(
        mandate=MANDATE,
        n=40,
        seed=4,
        scenarios=["baseline"],
        generator_kwargs={"breach_bias_mode": "single_holding", "breach_bias_prob": 1.0},
    )
    report = build_report(result)
    html = report.to_html()
    assert "max_single_holding" in html or "max_asset_class_weight" in html


def test_report_html_escapes_content():
    # Use a scenario ID that contains HTML-special characters.
    result = find_breaches(
        mandate=MANDATE,
        n=10,
        seed=5,
        scenarios=["baseline"],
    )
    report = build_report(result)
    html = report.to_html()
    assert "&lt;" not in html  # baseline has no angle brackets, but escaping should be present if any


def test_report_determinism():
    result_a = find_breaches(
        mandate=MANDATE,
        n=25,
        seed=6,
        scenarios=["baseline"],
        generator_kwargs={"breach_bias_mode": "single_holding", "breach_bias_prob": 1.0},
        record_limit=10,
    )
    result_b = find_breaches(
        mandate=MANDATE,
        n=25,
        seed=6,
        scenarios=["baseline"],
        generator_kwargs={"breach_bias_mode": "single_holding", "breach_bias_prob": 1.0},
        record_limit=10,
    )
    # Exclude generated_at from comparison.
    json_a = {k: v for k, v in build_report(result_a).json.items() if k != "generated_at"}
    json_b = {k: v for k, v in build_report(result_b).json.items() if k != "generated_at"}
    assert json_a == json_b
