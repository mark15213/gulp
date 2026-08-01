import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FeedEntry, Snapshot } from "@gulp/api-client";
import { EntryRow } from "./EntryRow";
import { SnapshotRow } from "./SnapshotRow";

afterEach(cleanup);

const entry = (over: Partial<FeedEntry> = {}): FeedEntry =>
  ({
    id: "e1",
    subscription_id: "sub1",
    subscription_title: "arXiv cs.AI",
    title: "Retrieval-augmented planning",
    url: "https://example.com/1",
    author: null,
    published_at: null,
    content_html: null,
    read: false,
    skipped: false,
    promoted_source_id: null,
    created_at: "2026-08-01T00:00:00Z",
    ...over,
  }) as FeedEntry;

const snap = (over: Partial<Snapshot> = {}): Snapshot =>
  ({
    id: "s1",
    kind: "snapshot",
    title: "Attention Is All You Need",
    note: null,
    status: "unprocessed",
    media_type: "pdf",
    genre: null,
    origin_url: "https://arxiv.org/abs/1706.03762",
    content_body: null,
    captured_via: "feed",
    cards_status: null,
    tags: [],
    source_feed: { id: "sub1", title: "arXiv cs.AI" },
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...over,
  }) as Snapshot;

const noop = () => {};

describe("EntryRow — stage 1 decides on the row", () => {
  it("offers Forward and Skip while pending", () => {
    render(
      <EntryRow
        entry={entry()}
        selected={false}
        cursor={false}
        onSelect={noop}
        onForward={noop}
        onSkip={noop}
      />,
    );
    expect(screen.getByRole("button", { name: "Forward" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Skip" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  });

  it("replaces both with Undo once skipped", () => {
    render(
      <EntryRow
        entry={entry({ skipped: true })}
        selected={false}
        cursor={false}
        onSelect={noop}
        onForward={noop}
        onSkip={noop}
      />,
    );
    expect(screen.getByRole("button", { name: "Undo" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Forward" })).toBeNull();
  });

  it("cannot forward an entry with no URL", () => {
    render(
      <EntryRow
        entry={entry({ url: null })}
        selected={false}
        cursor={false}
        onSelect={noop}
        onForward={noop}
        onSkip={noop}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Forward" }).hasAttribute("disabled"),
    ).toBe(true);
  });

  it("opens the decision preview from the title", async () => {
    const onSelect = vi.fn();
    render(
      <EntryRow
        entry={entry()}
        selected={false}
        cursor={false}
        onSelect={onSelect}
        onForward={noop}
        onSkip={noop}
      />,
    );
    await userEvent.click(screen.getByText("Retrieval-augmented planning"));
    expect(onSelect).toHaveBeenCalled();
  });
});

describe("SnapshotRow — the title is the way into the reader", () => {
  it("links the title to /snapshots/{id} at any status", () => {
    render(
      <SnapshotRow
        item={snap({ status: "processing" })}
        stage="flight"
        selected={false}
        cursor={false}
        onSelect={noop}
      />,
    );
    expect(
      screen.getByRole("link", { name: "Attention Is All You Need" }).getAttribute("href"),
    ).toBe("/snapshots/s1");
  });

  it("shows provenance from the emitting feed", () => {
    render(
      <SnapshotRow item={snap()} stage="kept" selected={false} cursor={false} onSelect={noop} />,
    );
    expect(screen.getByText("arXiv cs.AI")).toBeDefined();
  });

  it("falls back to the origin host for ad-hoc captures", () => {
    render(
      <SnapshotRow
        item={snap({ source_feed: null })}
        stage="kept"
        selected={false}
        cursor={false}
        onSelect={noop}
      />,
    );
    expect(screen.getByText("arxiv.org")).toBeDefined();
  });

  it("gives in-flight rows no actions at all", () => {
    render(
      <SnapshotRow
        item={snap({ status: "processing" })}
        stage="flight"
        selected={false}
        cursor={false}
        onSelect={noop}
      />,
    );
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("processing")).toBeDefined();
  });

  it("turns into Ready · Read → when it lands (the belt's last frame)", () => {
    render(
      <SnapshotRow
        item={snap({ status: "ready" })}
        stage="flight"
        done
        selected={false}
        cursor={false}
        onSelect={noop}
      />,
    );
    expect(screen.getByText("ready")).toBeDefined();
    expect(screen.getByRole("link", { name: "Read →" }).getAttribute("href")).toBe(
      "/snapshots/s1",
    );
  });

  it("offers Retry rather than Start when extraction failed", () => {
    render(
      <SnapshotRow
        item={snap({ status: "needs_attention" })}
        stage="needs"
        selected={false}
        cursor={false}
        onSelect={noop}
        onStart={noop}
      />,
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeDefined();
    expect(screen.getByText("needs attention")).toBeDefined();
  });

  it("only Kept rows are batch-selectable", () => {
    const { rerender } = render(
      <SnapshotRow
        item={snap()}
        stage="kept"
        selected={false}
        cursor={false}
        checked={false}
        onCheck={noop}
        onSelect={noop}
      />,
    );
    expect(screen.getByRole("checkbox")).toBeDefined();
    rerender(
      <SnapshotRow
        item={snap({ status: "processing" })}
        stage="flight"
        selected={false}
        cursor={false}
        onSelect={noop}
      />,
    );
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});
