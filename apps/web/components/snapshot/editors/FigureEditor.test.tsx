import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FigureEditor } from "./FigureEditor";

vi.mock("@gulp/api-client", () => ({
  getFigures: vi.fn(async () => [
    { id: "fig-1", label: "Figure 1", caption: "c", mime_type: "image/png", width: 10, height: 10 },
  ]),
  figureUrl: (s: string, f: string) => `/api/${s}/figures/${f}`,
}));

describe("FigureEditor gallery", () => {
  beforeEach(() => vi.clearAllMocks());

  it("attaches a picked figure_id on save", async () => {
    const onSave = vi.fn();
    render(
      <FigureEditor
        snapshotId="00000000-0000-0000-0000-000000000001"
        block={{ id: "b1", type: "figure", label: "L", explanation: "E", figure_id: null }}
        onSave={onSave}
        onCancel={() => {}}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Figure 1/i }));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ type: "figure", figure_id: "fig-1" }),
      ),
    );
  });
});
