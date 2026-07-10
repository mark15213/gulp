import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { FeedEntry } from "@gulp/api-client";
import { EntryList } from "./EntryList";

afterEach(() => cleanup());

const entry = (over: Partial<FeedEntry>): FeedEntry =>
  ({
    id: "e1",
    subscription_id: "s1",
    subscription_title: "Anthropic Research",
    title: "A post",
    url: "https://example.com/1",
    author: null,
    published_at: "2026-07-08T10:00:00Z",
    content_html: null,
    read: false,
    promoted_source_id: null,
    created_at: "2026-07-08T10:05:00Z",
    ...over,
  }) as FeedEntry;

const noop = () => {};

describe("EntryList", () => {
  it("shows unread state and selects", () => {
    const onSelect = vi.fn();
    render(
      <EntryList
        entries={[entry({})]}
        selectedId={null}
        onSelect={onSelect}
        unreadOnly={false}
        onToggleUnreadOnly={noop}
      />,
    );
    expect(screen.getByLabelText("unread")).toBeDefined();
    fireEvent.click(screen.getByText("A post"));
    expect(onSelect).toHaveBeenCalledWith("e1");
  });

  it("marks promoted entries as forwarded", () => {
    render(
      <EntryList
        entries={[entry({ promoted_source_id: "snap1", read: true })]}
        selectedId={null}
        onSelect={noop}
        unreadOnly={false}
        onToggleUnreadOnly={noop}
      />,
    );
    expect(screen.getByLabelText("forwarded")).toBeDefined();
    expect(screen.queryByLabelText("unread")).toBeNull();
  });

  it("offers mark-all-read only when provided", () => {
    const onMarkAllRead = vi.fn();
    render(
      <EntryList
        entries={[entry({})]}
        selectedId={null}
        onSelect={noop}
        unreadOnly={false}
        onToggleUnreadOnly={noop}
        onMarkAllRead={onMarkAllRead}
      />,
    );
    fireEvent.click(screen.getByText("Mark all read"));
    expect(onMarkAllRead).toHaveBeenCalled();
  });
});
