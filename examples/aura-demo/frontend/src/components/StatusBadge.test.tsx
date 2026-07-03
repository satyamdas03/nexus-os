import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders aligned label for green", () => {
    render(<StatusBadge status="green" />);
    expect(screen.getByText("ALIGNED")).toBeInTheDocument();
  });

  it("renders breached label for red", () => {
    render(<StatusBadge status="red" />);
    expect(screen.getByText("BREACH")).toBeInTheDocument();
  });

  it("renders attention label for orange", () => {
    render(<StatusBadge status="orange" />);
    expect(screen.getByText("ATTENTION")).toBeInTheDocument();
  });
});