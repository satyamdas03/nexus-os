import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AdviserChat } from "./AdviserChat";
import * as apiModule from "@/lib/api";

describe("AdviserChat", () => {
  it("sends a message and renders the assistant answer", async () => {
    vi.spyOn(apiModule.api.adviser, "chat").mockResolvedValueOnce({ answer: "You could trim AAPL to fix the single-holding breach." });

    render(<AdviserChat clientId="c00001" />);
    const input = screen.getByPlaceholderText(/Ask about this portfolio/);
    fireEvent.change(input, { target: { value: "How do I fix the breach?" } });
    fireEvent.click(screen.getByRole("button", { name: /Ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/How do I fix the breach?/)).toBeInTheDocument();
      expect(screen.getByText(/You could trim AAPL/)).toBeInTheDocument();
    });
  });
});
