"""Shared type definitions for the ASSURE kernel."""

from enum import Enum


class Status(str, Enum):
    OK = "ok"
    WATCH = "watch"
    BREACH = "breach"


class LegacyStatus(str, Enum):
    """Status vocabulary used by the original aura-demo."""
    GREEN = "green"
    ORANGE = "orange"
    RED = "red"


class Severity(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    WATCH = "watch"


class RuleType(str, Enum):
    MAX_ASSET_CLASS_WEIGHT = "max_asset_class_weight"
    MAX_SECTOR_WEIGHT = "max_sector_weight"
    APPROVED_UNIVERSE = "approved_universe"
    MAX_SINGLE_HOLDING = "max_single_holding"
    MIN_CASH = "min_cash"
    TARGET_ALLOCATION_DRIFT = "target_allocation_drift"
    MAX_REGION_WEIGHT = "max_region_weight"
    ESG_EXCLUSIONS = "esg_exclusions"
    MAX_TOP_N_CONCENTRATION = "max_top_n_concentration"
    MIN_LIQUID_PCT = "min_liquid_pct"
