import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ConfidenceCard } from "./ConfidenceCard";
import type { ConfidenceResult } from "@/lib/types";

const result: ConfidenceResult = {
  confidence: 0.82,
  rule_engine_certainty: 0.95,
  simulation_baseline: 0.85,
  historical_approval_success: 0.9,
  data_freshness: 1.0,
  human_review_recommended: false,
  explanation: "Rules engine is certain and recent data is fresh.",
  factors: [
    { name: "Rules engine", score: 0.95, weight: 0.35 },
    { name: "Simulation", score: 0.85, weight: 0.35 },
    { name: "History", score: 0.9, weight: 0.2 },
    { name: "Freshness", score: 1.0, weight: 0.1 },
  ],
};

describe("ConfidenceCard", () => {
  it("renders overall confidence and factors", () => {
    render(<ConfidenceCard result={result} />);
    expect(screen.getByText("AI Confidence")).toBeInTheDocument();
    expect(screen.getByText("High confidence")).toBeInTheDocument();
    expect(screen.getByText("Overall")).toBeInTheDocument();
    result.factors.forEach((f) => {
      expect(screen.getByText(f.name)).toBeInTheDocument();
    });
    expect(screen.getByText(/Rules engine is certain/)).toBeInTheDocument();
  });

  it("shows human-review banner when score is low", () => {
    const low: ConfidenceResult = { ...result, confidence: 0.55, human_review_recommended: true };
    render(<ConfidenceCard result={low} />);
    expect(screen.getByText("Human review recommended")).toBeInTheDocument();
  });
});
