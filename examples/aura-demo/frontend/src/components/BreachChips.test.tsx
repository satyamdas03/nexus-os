import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BreachChips } from "./BreachChips";
import type { Breach } from "@/lib/types";

const breaches: Breach[] = [
  { rule: "max_single_holding", plain: "Single holding > 10%", severity: "red", offending_holdings: ["AAPL"] },
  { rule: "min_cash", plain: "Cash below minimum", severity: "orange", offending_holdings: [] },
];

describe("BreachChips", () => {
  it("renders breach chips when items exist", () => {
    render(<BreachChips items={breaches} onPick={() => {}} />);
    expect(screen.getByText("Single holding > 10%")).toBeInTheDocument();
    expect(screen.getByText("Cash below minimum")).toBeInTheDocument();
  });

  it("does not render explain buttons without clientId", () => {
    render(<BreachChips items={breaches} onPick={() => {}} />);
    expect(screen.queryByLabelText(/Explain max_single_holding/)).not.toBeInTheDocument();
  });

  it("renders explain buttons when clientId is provided", () => {
    render(<BreachChips items={breaches} onPick={() => {}} clientId="c00001" />);
    expect(screen.getByLabelText("Explain max_single_holding")).toBeInTheDocument();
  });

  it("returns null when items array is empty", () => {
    const { container } = render(<BreachChips items={[]} onPick={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
