"""Verdict parsing and Reality Checker gate helpers."""

from __future__ import annotations

from nexus_os.pipeline.models import Verdict

REALITY_KEYWORDS: dict[Verdict, list[str]] = {
    Verdict.PASS: ["pass", "ready", "approved"],
    Verdict.FAIL: ["fail", "rejected"],
    Verdict.NEEDS_WORK: ["needs work", "needs_work", "not ready"],
    Verdict.NOT_READY: ["not ready", "not_ready"],
}


def parse_verdict(text: str) -> Verdict:
    """Parse a Verdict from free text."""
    upper = text.upper()
    # Reality Checker defaults to skepticism.
    if any(kw.upper() in upper for kw in REALITY_KEYWORDS[Verdict.NOT_READY]):
        return Verdict.NOT_READY
    if any(kw.upper() in upper for kw in REALITY_KEYWORDS[Verdict.NEEDS_WORK]):
        return Verdict.NEEDS_WORK
    if any(kw.upper() in upper for kw in REALITY_KEYWORDS[Verdict.FAIL]):
        return Verdict.FAIL
    if any(kw.upper() in upper for kw in REALITY_KEYWORDS[Verdict.PASS]):
        return Verdict.PASS
    return Verdict.NEEDS_WORK


class RealityChecker:
    """Evidence-based final gate. Defaults to NEEDS_WORK unless overwhelming proof."""

    @staticmethod
    def judge(evidence: list[str]) -> Verdict:
        """Return verdict based on evidence strings."""
        if not evidence:
            return Verdict.NEEDS_WORK
        # If every evidence item is a PASS, accept; otherwise default to NEEDS_WORK.
        for item in evidence:
            if parse_verdict(item) != Verdict.PASS:
                return Verdict.NEEDS_WORK
        return Verdict.PASS
