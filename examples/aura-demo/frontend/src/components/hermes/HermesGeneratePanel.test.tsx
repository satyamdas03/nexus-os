import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { HermesGeneratePanel } from "./HermesGeneratePanel";
import * as apiModule from "@/lib/api";
import type { HermesGenerateResult, HermesGenerateJob } from "@/lib/types";

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

const runningJob: HermesGenerateJob = {
  job_id: "abc123",
  status: "running",
  started_ts: "2026-07-05T00:00:00Z",
};

const doneJob: HermesGenerateJob = {
  job_id: "abc123",
  status: "done",
  started_ts: "2026-07-05T00:00:00Z",
  done_ts: "2026-07-05T00:00:05Z",
  result: generateResult,
};

describe("HermesGeneratePanel", () => {
  it("renders generate button", () => {
    render(<HermesGeneratePanel />);
    expect(screen.getByRole("button", { name: /Generate strategy diff/i })).toBeInTheDocument();
  });

  it("shows diff and generated test after polling job to done", async () => {
    vi.spyOn(apiModule.api.hermes, "generate").mockResolvedValueOnce({ job_id: "abc123" });
    const jobSpy = vi.spyOn(apiModule.api.hermes, "generateJob");
    jobSpy
      .mockResolvedValueOnce(runningJob)
      .mockResolvedValueOnce(runningJob)
      .mockResolvedValueOnce(doneJob);
    vi.spyOn(apiModule.api.hermes, "runTest").mockResolvedValueOnce({ ok: true, stdout: "", stderr: "", returncode: 0 });
    vi.spyOn(apiModule.api.hermes, "adopt").mockResolvedValueOnce({} as any);

    render(<HermesGeneratePanel />);
    fireEvent.click(screen.getByRole("button", { name: /Generate strategy diff/i }));

    await waitFor(() => {
      expect(screen.getByText(/trim_method/)).toBeInTheDocument();
      expect(screen.getByText(/largest_relative/)).toBeInTheDocument();
      expect(screen.getByText(/def test_strategy/)).toBeInTheDocument();
    }, { timeout: 5000 });

    fireEvent.click(screen.getByRole("button", { name: /Adopt as next version/i }));
    await waitFor(() => {
      expect(apiModule.api.hermes.adopt).toHaveBeenCalledWith({
        variable: "trim_method",
        to: "largest_relative",
        rationale: "Reduces reactive incidence in synthetic backtest.",
      });
    });
  });

  it("shows error when job fails", async () => {
    vi.spyOn(apiModule.api.hermes, "generate").mockResolvedValueOnce({ job_id: "abc123" });
    vi.spyOn(apiModule.api.hermes, "generateJob").mockResolvedValue({
      job_id: "abc123",
      status: "failed",
      started_ts: "2026-07-05T00:00:00Z",
      error: "simulation crashed",
    });

    render(<HermesGeneratePanel />);
    fireEvent.click(screen.getByRole("button", { name: /Generate strategy diff/i }));

    await waitFor(() => {
      expect(screen.getByText(/simulation crashed/)).toBeInTheDocument();
    });
  });
});
