import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { FigureAssetOut } from "@gulp/api-client";
import { InsertFigureMenu } from "./InsertFigureMenu";

vi.mock("@gulp/api-client", () => ({
  figureUrl: (s: string, f: string) => `/api/${s}/figures/${f}`,
}));

afterEach(cleanup);

const figs: FigureAssetOut[] = [
  { id: "f1", label: "Figure 1", caption: "c", mime_type: "image/png", width: 4, height: 4 },
];

describe("InsertFigureMenu", () => {
  it("renders nothing when there are no figures", () => {
    const { container } = render(
      <InsertFigureMenu snapshotId="s" figures={[]} onPick={() => {}} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("opens the gallery and picks a figure", () => {
    const onPick = vi.fn();
    render(<InsertFigureMenu snapshotId="s" figures={figs} onPick={onPick} />);
    expect(screen.queryByRole("button", { name: "Figure 1" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /insert figure below/i }));
    fireEvent.click(screen.getByRole("button", { name: "Figure 1" }));
    expect(onPick).toHaveBeenCalledWith(figs[0]);
    expect(screen.queryByRole("button", { name: "Figure 1" })).toBeNull(); // closed
  });
});
