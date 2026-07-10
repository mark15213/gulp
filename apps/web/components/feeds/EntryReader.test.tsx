import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { FeedEntry } from "@gulp/api-client";
import { EntryReader } from "./EntryReader";

afterEach(() => cleanup());

const entry = (over: Partial<FeedEntry>): FeedEntry =>
  ({
    id: "e1",
    subscription_id: "s1",
    subscription_title: "Anthropic Research",
    title: "A post",
    url: "https://example.com/1",
    author: null,
    published_at: null,
    content_html: "<p>hi</p>",
    read: false,
    promoted_source_id: null,
    promoted_status: null,
    created_at: "2026-07-08T10:05:00Z",
    ...over,
  }) as FeedEntry;

const noop = () => {};

describe("EntryReader", () => {
  it("offers the Forward action before an entry is forwarded", () => {
    render(<EntryReader entry={entry({})} onGulp={noop} onToggleRead={noop} />);
    expect(screen.getByRole("button", { name: "Forward" })).toBeDefined();
  });

  it("shows Processing while the promoted snapshot is still in the pipeline", () => {
    render(
      <EntryReader
        entry={entry({ promoted_source_id: "snap1", promoted_status: "processing" })}
        onGulp={noop}
        onToggleRead={noop}
      />,
    );
    expect(screen.getByText(/Processing/)).toBeDefined();
    // never claims the library prematurely, and the Forward button is gone
    expect(screen.queryByText(/In library/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Forward" })).toBeNull();
  });

  it("shows In library once the snapshot is ready", () => {
    render(
      <EntryReader
        entry={entry({ promoted_source_id: "snap1", promoted_status: "ready" })}
        onGulp={noop}
        onToggleRead={noop}
      />,
    );
    const link = screen.getByText(/In library/);
    expect(link.getAttribute("href")).toBe("/snapshots/snap1");
  });
});
