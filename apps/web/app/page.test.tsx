import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import * as api from "@gulp/api-client";
import TodayPage from "./page";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, getToday: vi.fn(), getCurrentGulpSession: vi.fn() };
});

const snap = (over: Record<string, unknown>) => ({
  id: "s1",
  kind: "snapshot",
  title: "The Bitter Lesson",
  note: null,
  status: "ready",
  media_type: null,
  origin_url: "https://a.com/x",
  content_body: null,
  captured_via: "in_app",
  cards_status: null,
  tags: [],
  created_at: "2026-07-02T00:00:00Z",
  updated_at: "2026-07-02T00:00:00Z",
  ...over,
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("TodayPage", () => {
  it("renders live counts, digest, and recents", async () => {
    (api.getToday as ReturnType<typeof vi.fn>).mockResolvedValue({
      accepted_cards: 4,
      card_sources: 2,
      ready_count: 2,
      digest: [{ snapshot: snap({}), accepted_cards: 4 }],
      inbox_count: 1,
      recent: [snap({ id: "s2", status: "processing", title: "Import AI" })],
      due_count: 12,
      new_count: 3,
      mastery: { new: 15, learning: 29, known: 84, at_risk: 5 },
    });
    (api.getCurrentGulpSession as ReturnType<typeof vi.fn>).mockResolvedValue(
      null,
    );
    render(await TodayPage());
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("The Bitter Lesson")).toBeTruthy();
    expect(screen.getByText("Import AI")).toBeTruthy();
    // Start/Resume CTA: live due/new counts, "Start" when no session in progress.
    const startLink = screen.getByRole("link", { name: /Start Gulp/ });
    expect(startLink.getAttribute("href")).toBe("/gulp");
    expect(startLink.querySelector("button")).toBeNull();
    expect(screen.getByText("12")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
    // Mastery tally.
    expect(screen.getByText("84 known")).toBeTruthy();
    expect(screen.getByText("29 learning")).toBeTruthy();
    expect(screen.getByText("15 new")).toBeTruthy();
    expect(screen.getByText("5 at risk")).toBeTruthy();
  });

  it("falls back to Note when a recent item has a malformed origin URL", async () => {
    (api.getToday as ReturnType<typeof vi.fn>).mockResolvedValue({
      accepted_cards: 0,
      card_sources: 0,
      ready_count: 0,
      digest: [],
      inbox_count: 1,
      recent: [
        snap({
          id: "s2",
          title: "Malformed source",
          status: "processing",
          origin_url: "not a valid URL",
        }),
      ],
      due_count: 0,
      new_count: 0,
      mastery: { new: 0, learning: 0, known: 0, at_risk: 0 },
    });
    (api.getCurrentGulpSession as ReturnType<typeof vi.fn>).mockResolvedValue(
      null,
    );

    render(await TodayPage());

    expect(screen.getByText("Malformed source")).toBeTruthy();
    expect(screen.getByText("Note")).toBeTruthy();
  });

  it("shows Resume when a session is already in progress", async () => {
    (api.getToday as ReturnType<typeof vi.fn>).mockResolvedValue({
      accepted_cards: 4,
      card_sources: 2,
      ready_count: 2,
      digest: [],
      inbox_count: 0,
      recent: [],
      due_count: 2,
      new_count: 0,
      mastery: { new: 0, learning: 0, known: 0, at_risk: 0 },
    });
    (api.getCurrentGulpSession as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "sess1",
      scope_type: "daily",
      target_minutes: 5,
      status: "in_progress",
      started_at: "2026-07-06T00:00:00Z",
      cards: [],
    });
    render(await TodayPage());
    const resumeLink = screen.getByRole("link", { name: /Resume Gulp/ });
    expect(resumeLink.getAttribute("href")).toBe("/gulp");
    expect(resumeLink.querySelector("button")).toBeNull();
  });

  it("still renders when the session lookup fails", async () => {
    (api.getToday as ReturnType<typeof vi.fn>).mockResolvedValue({
      accepted_cards: 0,
      card_sources: 0,
      ready_count: 0,
      digest: [],
      inbox_count: 0,
      recent: [],
      due_count: 0,
      new_count: 0,
      mastery: { new: 0, learning: 0, known: 0, at_risk: 0 },
    });
    (api.getCurrentGulpSession as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("network down"),
    );
    render(await TodayPage());
    expect(screen.getByText(/Nothing ready yet/)).toBeTruthy();
    expect(screen.getByText(/Inbox is clear/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /Start Gulp/ })).toBeTruthy();
  });
});
