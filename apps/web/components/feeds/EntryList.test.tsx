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

const pagination = {
  page: 0,
  pageSize: 50,
  totalCount: 1,
  loading: false,
  onPreviousPage: noop,
  onNextPage: noop,
};

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
        {...pagination}
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
        {...pagination}
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
        {...pagination}
      />,
    );
    fireEvent.click(screen.getByText("Mark all read"));
    expect(onMarkAllRead).toHaveBeenCalled();
  });

  it("exposes selected entry and unread-filter state", () => {
    render(
      <EntryList
        entries={[entry({})]}
        selectedId="e1"
        onSelect={noop}
        unreadOnly
        onToggleUnreadOnly={noop}
        {...pagination}
      />,
    );
    expect(
      screen
        .getByRole("button", { name: /A post/ })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(
      screen
        .getByRole("button", { name: "Unread" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("shows page status and enables the available direction", () => {
    const onPreviousPage = vi.fn();
    const onNextPage = vi.fn();
    render(
      <EntryList
        entries={[entry({})]}
        selectedId={null}
        onSelect={noop}
        unreadOnly={false}
        onToggleUnreadOnly={noop}
        page={1}
        pageSize={50}
        totalCount={120}
        loading={false}
        onPreviousPage={onPreviousPage}
        onNextPage={onNextPage}
      />,
    );

    expect(screen.getByText("Page 2 of 3 · 120 entries")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "← Previous" }));
    fireEvent.click(screen.getByRole("button", { name: "Next →" }));
    expect(onPreviousPage).toHaveBeenCalledOnce();
    expect(onNextPage).toHaveBeenCalledOnce();
  });
});
