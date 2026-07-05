"""Tests for the declarative mandate DSL."""

from pathlib import Path

import pytest

from assure_kernel import evaluate_portfolio
from assure_kernel.dsl import dump_mandate, load_mandate, parse_mandate, to_legacy_dict
from assure_kernel.models import Mandate, Rule


MANDATE_YAML = """
mandate:
  id: moderate-growth
  name: Moderate Growth
  version: 1.0.0
  metadata:
    author: test-suite
  rules:
    - id: equity-cap
      type: asset_class_weight
      enabled: true
      parameters:
        max_weights:
          Equity: 0.60
          FixedIncome: 0.40
    - id: tech-sector-cap
      type: sector_weight
      parameters:
        max_weights:
          Technology: 0.25
    - id: single-holding-cap
      type: single_holding
      parameters:
        max_weight: 0.10
    - id: min-cash
      type: minimum_cash
      parameters:
        min_weight: 0.05
"""


def test_parse_dsl_yaml():
    mandate = parse_mandate({"mandate": {"rules": [
        {"type": "asset_class_weight", "parameters": {"max_weights": {"Equity": 0.6}}}
    ]}})
    assert len(mandate.rules) == 1
    assert mandate.rules[0].type == "max_asset_class_weight"
    assert mandate.rules[0].params["weights"] == {"Equity": 0.6}


def test_load_dsl_from_file(tmp_path: Path):
    path = tmp_path / "mandate.yaml"
    path.write_text(MANDATE_YAML)
    mandate = load_mandate(path)
    assert mandate.id == "moderate-growth"
    assert len(mandate.rules) == 4


def test_dsl_evaluates_same_as_legacy():
    portfolio = {
        "cash": 10_000,
        "holdings": [
            {"ticker": "AAPL", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 200.0},
            {"ticker": "BND", "asset_class": "FixedIncome", "sector": "Bond", "units": 100, "price": 100.0},
        ],
    }
    dsl_mandate = parse_mandate({"mandate": {"rules": [
        {"type": "asset_class_weight", "parameters": {"max_weights": {"Equity": 0.6}}},
        {"type": "single_holding", "parameters": {"max_weight": 0.15}},
    ]}})
    legacy_mandate = {"max_asset_class_weight": {"Equity": 0.6}, "max_single_holding": 0.15}

    dsl_result = evaluate_portfolio(portfolio, dsl_mandate)
    legacy_result = evaluate_portfolio(portfolio, legacy_mandate)

    assert dsl_result.status == legacy_result.status


def test_to_legacy_dict_round_trip():
    mandate = Mandate(
        id="test",
        rules=[
            Rule(type="max_asset_class_weight", params={"weights": {"Equity": 0.6}}),
            Rule(type="min_cash", params={"limit": 0.05}),
        ],
    )
    legacy = to_legacy_dict(mandate)
    assert legacy["max_asset_class_weight"] == {"Equity": 0.6}
    assert legacy["min_cash"] == 0.05


def test_dump_mandate_creates_valid_yaml(tmp_path: Path):
    mandate = Mandate(
        id="dump-test",
        rules=[Rule(type="max_asset_class_weight", params={"weights": {"Equity": 0.6}})],
    )
    path = tmp_path / "out.yaml"
    dump_mandate(mandate, path)
    loaded = load_mandate(path)
    assert loaded.id == "dump-test"
    assert loaded.rules[0].type == "max_asset_class_weight"


@pytest.mark.parametrize(
    "bad_type",
    ["unknown_rule", "magic"],
)
def test_unknown_dsl_rule_type_raises(bad_type):
    with pytest.raises(ValueError):
        parse_mandate({"mandate": {"rules": [{"type": bad_type, "parameters": {}}]}})
