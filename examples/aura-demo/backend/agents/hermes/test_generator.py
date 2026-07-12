"""Generate a pytest regression test from a strategy diff."""
from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GENERATED_DIR = ROOT / "generated_tests"


def generate_test(diff: dict, simulation: dict, seed: int = 42) -> dict:
    """Write a generated pytest file and return its filename + source."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    var = diff["variable"]
    mode = diff.get("mode", "prevent")
    filename = f"test_strategy_{var}_{ts}.py"
    path = GENERATED_DIR / filename

    if mode == "reactive":
        before = simulation.get("reactive_incidence", 0) or 0
        after = simulation.get("reactive_incidence_after", 0) or 0
        mode_arg = "reactive"
        incidence_key = "reactive_incidence"
    else:
        before = simulation.get("prevent_incidence_before", 0) or 0
        after = simulation.get("prevent_incidence_after", 0) or 0
        mode_arg = "prevent"
        incidence_key = "prevent_incidence"

    threshold = int(after * 1.05) if after else before

    source = textwrap.dedent(f'''\
        """Generated regression test for strategy change: {var}."""
        from agents.hermes.strategy_io import load_strategy
        from agents.hermes.loop import simulate_book

        def test_strategy_change_lowers_incidence():
            baseline = load_strategy()
            baseline_result = simulate_book(days=30, mode="{mode_arg}", seed={seed}, strategy=baseline)
            baseline_incidence = baseline_result.get("{incidence_key}", 0) or 0

            candidate = dict(baseline)
            candidate["variables"]["{var}"]["value"] = {repr(diff["to"])}
            candidate_result = simulate_book(days=30, mode="{mode_arg}", seed={seed}, strategy=candidate)
            candidate_incidence = candidate_result.get("{incidence_key}", 0) or 0

            assert candidate_incidence <= {threshold}, (
                f"Expected candidate incidence <= {threshold}, got {{candidate_incidence}}"
            )
            assert candidate_incidence <= baseline_incidence, (
                f"Candidate incidence {{candidate_incidence}} should not exceed baseline {{baseline_incidence}}"
            )
        ''')

    path.write_text(source, encoding="utf-8")
    return {"filename": filename, "source": source}


def run_generated_test(source: str, timeout: int = 120) -> dict:
    """Run a generated test source in a temporary pytest process."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(source)
        f.flush()
        test_path = f.name

    try:
        proc = subprocess.run(
            ["python", "-m", "pytest", test_path, "-v"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stdout": "",
            "stderr": f"Test timed out after {timeout}s",
            "returncode": -1,
        }
    finally:
        try:
            os.unlink(test_path)
        except OSError:
            pass
