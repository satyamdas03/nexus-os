import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AdviserCanvas } from "./AdviserCanvas";
import type { AdviserWhiteboard } from "@/lib/types";

const whiteboard: AdviserWhiteboard = {
  client_id: "c00001",
  client_name: "Test Family Office",
  current_status: "red",
  post_status: "green",
  breaches: [
    {
      rule: "max_single_holding",
      explanation: "AAPL position exceeds 10% single-name limit.",
      offending_holdings: ["AAPL"],
    },
  ],
  proposed_trades: [
    { action: "sell", ticker: "AAPL", units: 50, value: 10000 },
  ],
};

describe("AdviserCanvas", () => {
  it("renders client name and status badges", () => {
    render(<AdviserCanvas whiteboard={whiteboard} />);
    expect(screen.getByText("Test Family Office")).toBeInTheDocument();
    expect(screen.getByText("BREACH")).toBeInTheDocument();
    expect(screen.getByText("ALIGNED")).toBeInTheDocument();
  });

  it("renders breaches and proposed trades", () => {
    render(<AdviserCanvas whiteboard={whiteboard} />);
    expect(screen.getByText(/max_single_holding/)).toBeInTheDocument();
    expect(screen.getByText(/AAPL position exceeds/)).toBeInTheDocument();
    expect(screen.getByText(/SELL/)).toBeInTheDocument();
    expect(screen.getAllByText(/AAPL/).length).toBeGreaterThanOrEqual(1);
  });

  it("renders empty state when no breaches or trades", () => {
    const empty: AdviserWhiteboard = {
      ...whiteboard,
      breaches: [],
      proposed_trades: [],
    };
    render(<AdviserCanvas whiteboard={empty} />);
    expect(screen.getByText("No breaches detected.")).toBeInTheDocument();
    expect(screen.getByText("No trades proposed.")).toBeInTheDocument();
  });
});
