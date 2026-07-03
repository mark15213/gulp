import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { BlockView } from "./BlockView";

vi.mock("@gulp/api-client", () => ({
  figureUrl: (s: string, f: string) => `/api/${s}/figures/${f}`,
}));

afterEach(cleanup);

describe("BlockView figure", () => {
  it("renders an img when figure_id is set", () => {
    render(
      <BlockView
        snapshotId="snap-1"
        block={{ id: "b1", type: "figure", label: "Fig 1", explanation: "e", figure_id: "fig-9" }}
      />,
    );
    const img = screen.getByRole("img");
    expect(img.getAttribute("src")).toBe("/api/snap-1/figures/fig-9");
  });

  it("stays text-only when figure_id is null", () => {
    render(
      <BlockView
        snapshotId="snap-1"
        block={{ id: "b1", type: "figure", label: "Fig 1", explanation: "e", figure_id: null }}
      />,
    );
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("Fig 1")).toBeTruthy();
  });
});
