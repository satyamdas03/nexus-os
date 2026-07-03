import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StatusDot } from "./StatusDot";

describe("StatusDot", () => {
  it.each([
    ["green", "bg-aura-emerald"],
    ["orange", "bg-aura-ochre"],
    ["red", "bg-aura-crimson"],
  ] as const)("renders %s status dot", (status, expectedClass) => {
    const { container } = render(<StatusDot status={status} />);
    expect(container.firstChild).toHaveClass("rounded-full");
    expect(container.firstChild).toHaveClass(expectedClass);
  });

  it("accepts additional className", () => {
    const { container } = render(<StatusDot status="green" className="scale-150" />);
    expect(container.firstChild).toHaveClass("scale-150");
  });
});
