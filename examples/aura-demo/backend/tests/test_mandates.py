# backend/tests/test_mandates.py
import random
from generators import mandates, universe


def test_every_template_builds_valid_mandate():
    rng = random.Random(123)
    for i in range(mandates.template_count()):
        m = mandates.build_mandate(rng, i)
        assert mandates.is_valid_mandate(m), f"template {i} invalid: {m}"


def test_mandate_covers_all_ten_rule_dims():
    m = mandates.build_mandate(random.Random(1), 0)
    for k in (
        "max_asset_class_weight", "max_sector_weight", "approved_universe",
        "max_single_holding", "min_cash", "target_allocation", "drift_tolerance",
        "max_region_weight", "excluded_tickers", "max_top_n_concentration",
        "min_liquid_pct",
    ):
        assert k in m, f"missing rule dim {k}"


def test_approved_universe_subset_of_real_tickers():
    real = set(universe.all_tickers())
    rng = random.Random(7)
    for i in range(mandates.template_count()):
        m = mandates.build_mandate(rng, i)
        assert set(m["approved_universe"]) <= real
        assert len(m["approved_universe"]) >= 4


def test_excluded_tickers_subset_of_approved():
    rng = random.Random(9)
    for i in range(mandates.template_count()):
        m = mandates.build_mandate(rng, i)
        assert set(m["excluded_tickers"]) <= set(m["approved_universe"])


def test_region_caps_only_real_regions():
    rng = random.Random(11)
    for i in range(mandates.template_count()):
        m = mandates.build_mandate(rng, i)
        for r in m["max_region_weight"]:
            assert r in universe.REGIONS


def test_randomization_varies_params_across_seeds():
    a = mandates.build_mandate(random.Random(1), 0)
    b = mandates.build_mandate(random.Random(2), 0)
    # at least one numeric cap differs across seeds
    assert a["max_single_holding"] != b["max_single_holding"] or a["min_cash"] != b["min_cash"]


def test_some_template_can_breach():
    """At least one template has caps tight enough that a plausible holding
    set breaches (sanity for the generator's breach cohort)."""
    tight = next(
        mandates.build_mandate(random.Random(3), i)
        for i in range(mandates.template_count())
        if mandates.build_mandate(random.Random(3), i)["max_single_holding"] <= 0.12
    )
    assert tight["max_single_holding"] <= 0.12