import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import * as api from "@gulp/api-client";
import type { FeedEntry } from "@gulp/api-client";
import { FeedsWorkspace } from "./FeedsWorkspace";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, getFeedEntries: vi.fn() };
});

const entry = (id: string, title: string): FeedEntry =>
  ({
    id,
    subscription_id: "s1",
    subscription_title: "Research",
    title,
    url: `https://example.com/${id}`,
    author: null,
    published_at: "2026-07-08T10:00:00Z",
    content_html: null,
    read: false,
    promoted_source_id: null,
    promoted_status: null,
    created_at: "2026-07-08T10:05:00Z",
  }) as FeedEntry;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("FeedsWorkspace pagination", () => {
  it("requests the next 50-entry page and replaces the visible entries", async () => {
    (api.getFeedEntries as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        items: [entry("e51", "Page two entry")],
        count: 60,
      })
      .mockResolvedValueOnce({
        items: [entry("e1", "Unread page one entry")],
        count: 1,
      });

    render(
      <FeedsWorkspace
        initialSubscriptions={[]}
        initialEntries={[entry("e1", "Page one entry")]}
        initialEntryCount={60}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Next →" }));

    await waitFor(() =>
      expect(api.getFeedEntries).toHaveBeenCalledWith({
        subscriptionId: undefined,
        unreadOnly: false,
        limit: 50,
        offset: 50,
      }),
    );
    expect(await screen.findByText("Page two entry")).toBeTruthy();
    expect(screen.queryByText("Page one entry")).toBeNull();
    expect(screen.getByText("Page 2 of 2 · 60 entries")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Unread" }));
    await waitFor(() =>
      expect(api.getFeedEntries).toHaveBeenNthCalledWith(2, {
        subscriptionId: undefined,
        unreadOnly: true,
        limit: 50,
        offset: 0,
      }),
    );
    expect(await screen.findByText("Unread page one entry")).toBeTruthy();
    expect(screen.getByText("Page 1 of 1 · 1 entry")).toBeTruthy();
  });
});
