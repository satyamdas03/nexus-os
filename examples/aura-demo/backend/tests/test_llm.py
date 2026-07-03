import json

from agents.llm import get_llm, MockLLM, ClaudeProvider, _mock_explain_narrative


def test_mock_explain_full_narrative_mentions_breaches():
    facts = {
        "client": "Acme #00001",
        "fum": 1_000_000,
        "holdings": [{"ticker": "NVDA", "weight_pct": 34.0}, {"ticker": "SPY", "weight_pct": 20.0}],
        "cash_pct": 4.0,
        "engine_breaches": [
            {"rule": "max_sector_weight:Technology", "current": 0.34, "limit": 0.25,
             "plain": "Technology 34% > 25% cap", "offending_holdings": ["NVDA"]},
            {"rule": "approved_universe", "current": ["AVAX"], "limit": ["SPY", "QQQ"],
             "plain": "AVAX not in approved list", "offending_holdings": ["AVAX"]},
        ],
        "engine_watches": [],
    }
    out = _mock_explain_narrative(json.dumps(facts, ensure_ascii=False))
    assert "Technology 34% > 25% cap (max_sector_weight:Technology)" in out
    assert "AVAX not in approved list (approved_universe)" in out
    assert "2 mandate breach" in out
    assert "Cash reserve is 4.0%" in out
    assert "NVDA (34.0%)" in out


def test_mock_explain_per_metric_row_pass():
    row = {"rule": "max_asset_class_weight:Equity", "pass": True,
           "current": 0.55, "limit": 0.80, "offending_holdings": []}
    user = f"Rules-engine row (GROUND TRUTH):\n{json.dumps(row, ensure_ascii=False)}\n\nWrite ONE plain-English sentence."
    out = _mock_explain_narrative(user)
    assert "Equity check passes" in out
    assert "is at 55.0%" in out
    assert "cap is 80.0%" in out


def test_mock_explain_per_metric_row_breach():
    row = {"rule": "max_region_weight:US", "pass": False,
           "current": 0.72, "limit": 0.60, "offending_holdings": ["SPY"]}
    user = f"Rules-engine row (GROUND TRUTH):\n{json.dumps(row, ensure_ascii=False)}\n\nWrite ONE plain-English sentence."
    out = _mock_explain_narrative(user)
    assert "US check breaches" in out
    assert "is at 72.0%" in out
    assert "cap is 60.0%" in out


def test_mock_llm_returns_text():
    m = MockLLM()
    out = m.complete("system", "user input")
    assert isinstance(out, str) and len(out) > 0


def test_factory_returns_mock_when_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = get_llm()
    assert isinstance(p, MockLLM)


def test_factory_returns_claude_when_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    p = get_llm()
    assert isinstance(p, ClaudeProvider)