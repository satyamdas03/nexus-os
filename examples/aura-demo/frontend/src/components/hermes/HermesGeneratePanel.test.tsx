import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { HermesGeneratePanel } from "./HermesGeneratePanel";
import * as apiModule from "@/lib/api";
import type { HermesGenerateResult } from "@/lib/types";

const generateResult: HermesGenerateResult = {
  ok: true,
  diff: {
    variable: "trim_method",
    from: "largest_absolute",
    to: "largest_relative",
    rationale: "Reduces reactive incidence in synthetic backtest.",
  },
  test: {
    filename: "test_trim_method_largest_relative.py",
    source: "def test_strategy(): assert True",
  },
  simulation: {
    reactive_incidence: 0.05,
    prevent_incidence_before: 0.08,
    prevent_incidence_after: 0.04,
    improvement_pct: 50,
  },
};

describe("HermesGeneratePanel", () => {
  it("renders generate button", () => {
    render(<HermesGeneratePanel />);
    expect(screen.getByRole("button", { name: /Generate strategy diff/i })).toBeInTheDocument();
  });

  it("shows diff and generated test after generate", async () => {
    vi.spyOn(apiModule.api.hermes, "generate").mockResolvedValueOnce(generateResult);
    vi.spyOn(apiModule.api.hermes, "adopt").mockResolvedValueOnce({} as any);

    render(<HermesGeneratePanel />);
    fireEvent.click(screen.getByRole("button", { name: /Generate strategy diff/i }));

    await waitFor(() => {
      expect(screen.getByText(/trim_method/)).toBeInTheDocument();
      expect(screen.getByText(/largest_relative/)).toBeInTheDocument();
      expect(screen.getByText(/def test_strategy/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Adopt as next version/i }));
    await waitFor(() => {
      expect(apiModule.api.hermes.adopt).toHaveBeenCalledWith({
        variable: "trim_method",
        to: "largest_relative",
        rationale: "Reduces reactive incidence in synthetic backtest.",
      });
    });
  });
});
