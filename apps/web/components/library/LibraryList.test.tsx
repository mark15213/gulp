import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Snapshot } from "@gulp/api-client";
import { LibraryList } from "./LibraryList";

afterEach(cleanup);

function item(overrides: Partial<Snapshot> = {}): Snapshot {
  return {
    id: "s1",
    kind: "snapshot",
    title: "ABot-M0.5",
    note: null,
    status: "ready",
    media_type: "pdf",
    origin_url: "https://arxiv.org/abs/1",
    content_body: null,
    captured_via: "paste",
    cards_status: null,
    tags: ["robotics"],
    created_at: "",
    updated_at: "",
    ...overrides,
  } as Snapshot;
}

describe("LibraryList", () => {
  it("renders shelved snapshots with links", () => {
    render(<LibraryList items={[item(), item({ id: "s2", title: "BERT", tags: ["nlp"] })]} />);
    expect(screen.getByRole("link", { name: "ABot-M0.5" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "BERT" })).toBeTruthy();
  });

  it("filters by tag chip and resets with All", async () => {
    render(<LibraryList items={[item(), item({ id: "s2", title: "BERT", tags: ["nlp"] })]} />);
    await userEvent.click(screen.getByRole("button", { name: "nlp" }));
    expect(screen.queryByText("ABot-M0.5")).toBeNull();
    expect(screen.getByText("BERT")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getByText("ABot-M0.5")).toBeTruthy();
  });

  it("shows the empty state", () => {
    render(<LibraryList items={[]} />);
    expect(screen.getByText(/Nothing here yet/)).toBeTruthy();
  });
});
