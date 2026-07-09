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

  it("renders a remote img when url is set without figure_id", () => {
    render(
      <BlockView
        snapshotId="snap-1"
        block={{
          id: "b1",
          type: "figure",
          label: "Diagram",
          explanation: "",
          figure_id: null,
          url: "https://x.test/a.png",
        }}
      />,
    );
    expect(screen.getByRole("img").getAttribute("src")).toBe("https://x.test/a.png");
  });
});

describe("BlockView code", () => {
  it("renders code content inside pre/code with the language tagged", () => {
    render(
      <BlockView
        snapshotId="snap-1"
        block={{ id: "b2", type: "code", language: "python", content: "x = 1" }}
      />,
    );
    const code = document.querySelector("pre > code")!;
    expect(code.textContent).toBe("x = 1");
    expect(code.getAttribute("data-language")).toBe("python");
  });
});
