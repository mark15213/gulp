import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FeedEntry, Snapshot, Subscription } from "@gulp/api-client";
import { InboxWorkspace } from "./InboxWorkspace";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

// vi.mock is hoisted above the module body, so the doubles must be too.
const api = vi.hoisted(() => ({
  createSubscription: vi.fn(),
  deleteSnapshot: vi.fn(),
  deleteSubscription: vi.fn(),
  getFeedEntries: vi.fn(),
  getInbox: vi.fn(),
  getSnapshot: vi.fn(),
  getSubscriptions: vi.fn(),
  gulpEntry: vi.fn(),
  patchSubscription: vi.fn(),
  processBatch: vi.fn(),
  refreshSubscription: vi.fn(),
  setEntryRead: vi.fn(),
  setEntrySkipped: vi.fn(),
  skipAllSubscription: vi.fn(),
  startProcessing: vi.fn(),
}));
vi.mock("@gulp/api-client", () => api);

afterEach(cleanup);

const sub = (over: Partial<Subscription> = {}): Subscription =>
  ({
    id: "sub1",
    title: "arXiv cs.AI",
    feed_url: "https://rss.arxiv.org/rss/cs.AI",
    health: "active",
    muted: false,
    pending_count: 1,
    last_fetch_at: null,
    last_fetch_error: null,
    created_at: "2026-08-01T00:00:00Z",
    ...over,
  }) as Subscription;

const entry = (over: Partial<FeedEntry> = {}): FeedEntry =>
  ({
    id: "e1",
    subscription_id: "sub1",
    subscription_title: "arXiv cs.AI",
    title: "Retrieval-augmented planning",
    url: "https://example.com/1",
    author: null,
    published_at: null,
    content_html: "<p>abstract</p>",
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
    origin_url: "https://arxiv.org/abs/1",
    content_body: null,
    captured_via: "feed",
    cards_status: null,
    tags: [],
    source_feed: { id: "sub1", title: "arXiv cs.AI" },
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...over,
  }) as Snapshot;

function mount(over: Partial<Parameters<typeof InboxWorkspace>[0]> = {}) {
  return render(
    <InboxWorkspace
      initialSubscriptions={[sub()]}
      initialEntries={[entry()]}
      initialEntryCount={1}
      initialItems={[
        snap(),
        snap({ id: "s2", title: "Bitter Lesson", status: "needs_attention" }),
        snap({ id: "s3", title: "Scaling Laws", status: "processing" }),
      ]}
      initialActionable={2}
      {...over}
    />,
  );
}

const section = (name: string) =>
  screen.getByRole("region", { name: "Intake stages" }).querySelectorAll("section")[
    ["New", "Kept", "Needs you", "In flight"].indexOf(name)
  ]!;

beforeEach(() => {
  window.localStorage.clear();
  Object.values(api).forEach((fn) => fn.mockReset());
  api.deleteSnapshot.mockResolvedValue(undefined);
  api.deleteSubscription.mockResolvedValue(undefined);
  api.patchSubscription.mockResolvedValue({});
  api.refreshSubscription.mockResolvedValue(undefined);
  api.setEntryRead.mockResolvedValue(undefined);
  api.setEntrySkipped.mockResolvedValue(undefined);
  api.skipAllSubscription.mockResolvedValue(undefined);
  api.startProcessing.mockResolvedValue({});
  api.getSubscriptions.mockResolvedValue({ items: [sub()], count: 1 });
  api.getFeedEntries.mockResolvedValue({ items: [entry()], count: 1 });
  api.getInbox.mockResolvedValue({ items: [], count: 0, actionable_count: 0 });
  api.gulpEntry.mockResolvedValue({ snapshot_id: "new1", duplicate: false, status: "unprocessed" });
  api.processBatch.mockResolvedValue({ started: ["s1"], skipped: [] });
  api.getSnapshot.mockResolvedValue(snap({ status: "ready" }));
});

describe("stage sections", () => {
  it("groups one /inbox response into Kept, Needs you and In flight", () => {
    mount();
    expect(within(section("Kept")).getByText("Attention Is All You Need")).toBeDefined();
    expect(within(section("Needs you")).getByText("Bitter Lesson")).toBeDefined();
    expect(within(section("In flight")).getByText("Scaling Laws")).toBeDefined();
  });

  it("collapses a section and remembers it", async () => {
    mount();
    const toggle = within(section("New")).getByRole("button", { expanded: true });
    await userEvent.click(toggle);
    expect(screen.queryByText("Retrieval-augmented planning")).toBeNull();
    expect(JSON.parse(window.localStorage.getItem("gulp.inbox.collapsed")!)).toEqual({
      new: true,
    });
  });
});

describe("the rail owns source, the sections own stage", () => {
  it("Captured hides New — ad-hoc intake has no stage 1", async () => {
    mount();
    expect(screen.getByText("Retrieval-augmented planning")).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: /Captured/ }));
    await waitFor(() => expect(api.getInbox).toHaveBeenCalledWith({
      emittedBy: undefined,
      adHocOnly: true,
    }));
    expect(screen.queryByText("Retrieval-augmented planning")).toBeNull();
    expect(screen.queryByText("New")).toBeNull();
  });

  it("scopes every section to the selected subscription", async () => {
    mount();
    await userEvent.click(screen.getByRole("button", { name: "arXiv cs.AI" }));
    await waitFor(() =>
      expect(api.getInbox).toHaveBeenCalledWith({ emittedBy: "sub1", adHocOnly: false }),
    );
    expect(api.getFeedEntries).toHaveBeenCalledWith(
      expect.objectContaining({ subscriptionId: "sub1", pendingOnly: true }),
    );
  });
});

describe("stage 1 → stage 2", () => {
  it("Forward moves the row out of New and refetches the sections", async () => {
    mount();
    await userEvent.click(screen.getByRole("button", { name: "Forward" }));
    await waitFor(() =>
      expect(screen.queryByText("Retrieval-augmented planning")).toBeNull(),
    );
    expect(api.gulpEntry).toHaveBeenCalledWith("e1");
    expect(api.getInbox).toHaveBeenCalled();
  });

  it("opening an entry marks it seen but keeps it in the queue", async () => {
    mount();
    await userEvent.click(within(section("New")).getByText("Retrieval-augmented planning"));
    expect(api.setEntryRead).toHaveBeenCalledWith("e1", true);
    // still in New — seen is not decided — and now also in the preview pane
    expect(within(section("New")).getByText("Retrieval-augmented planning")).toBeDefined();
    expect(
      within(screen.getByRole("complementary", { name: "Decision preview" })).getByRole(
        "heading",
        { name: "Retrieval-augmented planning" },
      ),
    ).toBeDefined();
  });

  it("Skip takes it out of pending, and is reversible", async () => {
    mount();
    await userEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(api.setEntrySkipped).toHaveBeenCalledWith("e1", true);
    await waitFor(() =>
      expect(screen.queryByText("Retrieval-augmented planning")).toBeNull(),
    );
  });
});

describe("stage 2 → the belt's last frame", () => {
  it("Start moves the row to In flight, then it lands as Ready · Read →", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mount();
    await userEvent.click(within(section("Kept")).getByRole("button", { name: "▶ Start" }));
    await waitFor(() => expect(api.startProcessing).toHaveBeenCalledWith("s1"));
    expect(within(section("In flight")).getByText("Attention Is All You Need")).toBeDefined();

    await vi.advanceTimersByTimeAsync(3200);
    await waitFor(() =>
      expect(within(section("In flight")).getByRole("link", { name: "Read →" })).toBeDefined(),
    );
    vi.useRealTimers();
  });

  it("starts a checked batch through one call", async () => {
    mount();
    await userEvent.click(within(section("Kept")).getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "▶ Start 1" }));
    await waitFor(() => expect(api.processBatch).toHaveBeenCalledWith(["s1"]));
  });
});

describe("keyboard — the list is the primary surface", () => {
  it("j moves the cursor and f forwards it", async () => {
    mount();
    const stages = screen.getByRole("region", { name: "Intake stages" });
    stages.focus();
    await userEvent.keyboard("j");
    await userEvent.keyboard("f");
    await waitFor(() => expect(api.gulpEntry).toHaveBeenCalledWith("e1"));
  });

  it("s skips the row under the cursor", async () => {
    mount();
    screen.getByRole("region", { name: "Intake stages" }).focus();
    await userEvent.keyboard("j");
    await userEvent.keyboard("s");
    await waitFor(() => expect(api.setEntrySkipped).toHaveBeenCalledWith("e1", true));
  });
});
