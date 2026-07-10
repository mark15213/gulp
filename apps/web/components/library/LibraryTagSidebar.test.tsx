import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { LibraryFacets } from "@/lib/libraryFacets";
import { LibraryTagSidebar } from "./LibraryTagSidebar";

afterEach(cleanup);

const facets: LibraryFacets = {
  sources: [{ value: "HF Paper Daily", count: 2 }],
  tags: [{ value: "pretrain", count: 3 }],
};

describe("LibraryTagSidebar", () => {
  it("renders Sources, Mine, and a disabled Topics placeholder", () => {
    render(
      <LibraryTagSidebar facets={facets} active={null} onSelect={() => {}} />,
    );
    expect(screen.getByText("Sources")).toBeTruthy();
    expect(screen.getByText("Mine")).toBeTruthy();
    expect(screen.getByText("Topics")).toBeTruthy();
    expect(screen.getByText("coming soon")).toBeTruthy();
    expect(screen.getByText("HF Paper Daily")).toBeTruthy();
  });

  it("selects a source filter on click", async () => {
    const onSelect = vi.fn();
    render(
      <LibraryTagSidebar facets={facets} active={null} onSelect={onSelect} />,
    );
    const source = screen.getByRole("button", { name: /HF Paper Daily/ });
    expect(source.getAttribute("aria-pressed")).toBe("false");
    expect(
      screen.getByRole("button", { name: "All" }).getAttribute("aria-pressed"),
    ).toBe("true");
    await userEvent.click(source);
    expect(onSelect).toHaveBeenCalledWith({
      kind: "source",
      value: "HF Paper Daily",
    });
  });

  it("toggles the active filter off when re-clicked", async () => {
    const onSelect = vi.fn();
    render(
      <LibraryTagSidebar
        facets={facets}
        active={{ kind: "tag", value: "pretrain" }}
        onSelect={onSelect}
      />,
    );
    const activeTag = screen.getByRole("button", { name: /pretrain/ });
    expect(activeTag.getAttribute("aria-pressed")).toBe("true");
    await userEvent.click(activeTag);
    expect(onSelect).toHaveBeenCalledWith(null);
  });
});
