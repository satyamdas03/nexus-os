"""Tests for the deterministic rule documentation renderer."""
from assure_kernel import Mandate, Rule, describe_mandate, describe_rule, rule_type_metadata
from assure_kernel.types import Severity


def test_rule_type_metadata_covers_builtin_rules():
    meta = rule_type_metadata()
    for rt in (
        "max_asset_class_weight",
        "max_sector_weight",
        "max_region_weight",
        "approved_universe",
        "esg_exclusions",
        "max_single_holding",
        "min_cash",
        "min_liquid_pct",
        "target_allocation_drift",
        "max_top_n_concentration",
    ):
        assert rt in meta, f"missing docs for {rt}"
        assert "title" in meta[rt]
        assert "summary" in meta[rt]


def test_describe_asset_class_rule():
    rule = Rule(type="max_asset_class_weight", params={"weights": {"Equity": 0.65, "Bonds": 0.35}})
    doc = describe_rule(rule)
    assert doc["type"] == "max_asset_class_weight"
    assert "Asset-class weight cap" == doc["title"]
    assert "Equity at 65.0%" in doc["description"]
    assert "Bonds at 35.0%" in doc["description"]
    assert doc["enabled"] is True
    assert doc["severity"] is None


def test_describe_rule_with_severity():
    rule = Rule(type="max_single_holding", params={"limit": 0.10}, severity=Severity.HARD)
    doc = describe_rule(rule)
    assert doc["severity"] == "hard breach"
    assert "10.0%" in doc["description"]


def test_describe_mandate():
    mandate = Mandate(
        id="test",
        name="Test Mandate",
        version="1.0.0",
        rules=[
            Rule(type="min_cash", params={"limit": 0.05}),
            Rule(type="approved_universe", params={"tickers": ["AAPL", "MSFT"]}),
        ],
    )
    doc = describe_mandate(mandate)
    assert doc["id"] == "test"
    assert doc["name"] == "Test Mandate"
    assert doc["rule_count"] == 2
    assert doc["enabled_rule_count"] == 2
    assert len(doc["rules"]) == 2
    assert doc["rules"][0]["title"] == "Minimum cash buffer"


def test_describe_unknown_rule_is_graceful():
    doc = describe_rule(Rule(type="custom:something", params={"foo": 1}))
    assert doc["type"] == "custom:something"
    assert doc["title"] == "custom:something"
    assert "Custom rule" in doc["summary"]
