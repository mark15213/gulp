import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import * as api from "@gulp/api-client";
import TodayPage from "./page";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, getToday: vi.fn() };
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
    });
    render(await TodayPage());
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("The Bitter Lesson")).toBeTruthy();
    expect(screen.getByText("Import AI")).toBeTruthy();
  });

  it("shows empty states", async () => {
    (api.getToday as ReturnType<typeof vi.fn>).mockResolvedValue({
      accepted_cards: 0,
      card_sources: 0,
      ready_count: 0,
      digest: [],
      inbox_count: 0,
      recent: [],
    });
    render(await TodayPage());
    expect(screen.getByText(/Nothing ready yet/)).toBeTruthy();
    expect(screen.getByText(/Inbox is clear/)).toBeTruthy();
  });
});
