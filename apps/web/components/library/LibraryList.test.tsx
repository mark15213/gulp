import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Snapshot } from "@gulp/api-client";
import { LibraryList } from "./LibraryList";

// Rows carry <DeleteSnapshotButton> (useRouter) and <RowTags> (api-client).
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("@gulp/api-client", () => ({
  addSnapshotTag: vi.fn().mockResolvedValue({}),
  removeSnapshotTag: vi.fn().mockResolvedValue({}),
  deleteSnapshot: vi.fn().mockResolvedValue(undefined),
}));

afterEach(cleanup);

const sidebar = () =>
  screen.getByRole("complementary", { name: "Filter library" });

function item(overrides: Partial<Snapshot> = {}): Snapshot {
  return {
    id: "s1",
    kind: "snapshot",
    title: "ABot-M0.5",
    note: null,
    status: "ready",
    media_type: "pdf",
    genre: null,
    origin_url: "https://arxiv.org/abs/1",
    content_body: null,
    captured_via: "paste",
    cards_status: null,
    tags: ["robotics"],
    source_feed: null,
    created_at: "",
    updated_at: "",
    ...overrides,
  } as Snapshot;
}

describe("LibraryList", () => {
  it("renders shelved snapshots with links", () => {
    render(
      <LibraryList
        items={[item(), item({ id: "s2", title: "BERT", tags: ["nlp"] })]}
      />,
    );
    expect(screen.getByRole("link", { name: "ABot-M0.5" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "BERT" })).toBeTruthy();
    expect(screen.getByRole("list")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("filters by a Mine tag entry and resets with All", async () => {
    render(
      <LibraryList
        items={[item(), item({ id: "s2", title: "BERT", tags: ["nlp"] })]}
      />,
    );
    const nlp = within(sidebar()).getByRole("button", { name: /nlp/ });
    await userEvent.click(nlp);
    expect(nlp.getAttribute("aria-pressed")).toBe("true");
    expect(screen.queryByRole("link", { name: "ABot-M0.5" })).toBeNull();
    expect(screen.getByRole("link", { name: "BERT" })).toBeTruthy();
    await userEvent.click(
      within(sidebar()).getByRole("button", { name: "All" }),
    );
    expect(screen.getByRole("link", { name: "ABot-M0.5" })).toBeTruthy();
  });

  it("filters by a Source entry", async () => {
    render(
      <LibraryList
        items={[
          item({
            id: "s1",
            title: "Paper A",
            source_feed: { id: "f1", title: "HF Paper Daily" },
            tags: [],
          }),
          item({ id: "s2", title: "Blog B", source_feed: null, tags: [] }),
        ]}
      />,
    );
    await userEvent.click(
      within(sidebar()).getByRole("button", { name: /HF Paper Daily/ }),
    );
    expect(screen.getByRole("link", { name: "Paper A" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Blog B" })).toBeNull();
  });

  it("shows the empty state", () => {
    render(<LibraryList items={[]} />);
    expect(screen.getByText(/Nothing here yet/)).toBeTruthy();
  });

  it("shows per-row badges (media_type + cards status)", () => {
    render(
      <LibraryList
        items={[item({ media_type: "video", cards_status: "generating" })]}
      />,
    );
    expect(screen.getByText("Video")).toBeTruthy();
    expect(screen.getByText("Cards…")).toBeTruthy();
  });
});
