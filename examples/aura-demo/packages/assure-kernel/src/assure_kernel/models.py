"""Pydantic models for the ASSURE kernel."""

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from assure_kernel.types import LegacyStatus, Severity, Status


class Holding(BaseModel):
    """A single position in a portfolio.

    Classification fields (asset_class, sector, region, liquidity_tier) are
    optional so the engine can evaluate only the rules that are applicable to
    the data actually present.
    """

    ticker: str
    units: float = 0.0
    price: float = 0.0
    market_value: float | None = None
    name: str | None = None
    asset_class: str | None = None
    sector: str | None = None
    region: str | None = None
    liquidity_tier: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def compute_market_value(self):
        if self.market_value is None:
            self.market_value = round(self.units * self.price, 2)
        return self


class Portfolio(BaseModel):
    """Portfolio state passed to the assurance engine."""

    client_id: str | None = None
    client_name: str | None = None
    adviser: str | None = None
    cash: float = 0.0
    holdings: list[Holding] = Field(default_factory=list)
    fum: float | None = None  # funds under management, advisory only

    @property
    def total_value(self) -> float:
        return sum(h.market_value or 0.0 for h in self.holdings) + self.cash


class Rule(BaseModel):
    """A single mandate rule."""

    type: str
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    severity: Severity | None = None
    message: str | None = None


class Mandate(BaseModel):
    """A mandate is a versioned collection of rules."""

    id: str | None = None
    name: str | None = None
    version: str = "1.0.0"
    rules: list[Rule] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class Violation(BaseModel):
    """A single rule violation produced by the engine."""

    rule: str
    current: Any
    limit: Any
    offending_holdings: list[str] = Field(default_factory=list)
    severity: Severity | None = None
    plain: str | None = None


class RuleEvaluation(BaseModel):
    """The result of evaluating one rule against one portfolio."""

    rule: str
    pass_: bool = Field(alias="pass")
    current: Any
    limit: Any
    offending_holdings: list[str] = Field(default_factory=list)
    severity: Severity | None = None
    n: int | None = None  # for top-n concentration

    @field_validator("pass_", mode="before")
    @classmethod
    def accept_pass_alias(cls, v):
        return v

    model_config = {"populate_by_name": True}


class RulesResult(BaseModel):
    """The deterministic output of the assurance engine."""

    status: Status
    breaches: list[Violation] = Field(default_factory=list)
    watches: list[Violation] = Field(default_factory=list)
    per_rule: list[RuleEvaluation] = Field(default_factory=list)

    def to_legacy(self) -> dict:
        """Convert kernel result to the original aura-demo dict shape.

        Preserves the legacy severity vocabulary: red/green/orange.
        """
        status_map = {
            Status.OK: LegacyStatus.GREEN,
            Status.WATCH: LegacyStatus.ORANGE,
            Status.BREACH: LegacyStatus.RED,
        }

        def _severity(v: Violation | RuleEvaluation) -> str:
            if v.severity == Severity.HARD:
                return "red"
            if v.severity == Severity.WATCH:
                return "orange"
            return "green"

        def _dump(item: Violation | RuleEvaluation) -> dict:
            d = item.model_dump(exclude_none=True, by_alias=isinstance(item, RuleEvaluation))
            d["severity"] = _severity(item)
            return d

        return {
            "status": status_map[self.status].value,
            "breaches": [_dump(b) for b in self.breaches],
            "watches": [_dump(w) for w in self.watches],
            "per_rule": [_dump(r) for r in self.per_rule],
        }

    @classmethod
    def from_legacy(cls, data: dict) -> "RulesResult":
        status_map = {
            LegacyStatus.GREEN.value: Status.OK,
            LegacyStatus.ORANGE.value: Status.WATCH,
            LegacyStatus.RED.value: Status.BREACH,
        }
        return cls(
            status=status_map.get(data["status"], Status.OK),
            breaches=[Violation(**v) for v in data.get("breaches", [])],
            watches=[Violation(**v) for v in data.get("watches", [])],
            per_rule=[RuleEvaluation(**r) for r in data.get("per_rule", [])],
        )
