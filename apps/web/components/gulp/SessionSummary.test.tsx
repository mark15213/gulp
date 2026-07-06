import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { GulpSummary } from "@gulp/api-client";
import { SessionSummary } from "./SessionSummary";

afterEach(cleanup);

const SUMMARY: GulpSummary = {
  reviewed_count: 5,
  newly_mastered: 2,
  still_fuzzy: 1,
  streak_days: 7,
  next_up: { due_count: 7, inbox_count: 4 },
};

describe("SessionSummary", () => {
  it("renders the reviewed / mastered / fuzzy / streak stats", () => {
    render(<SessionSummary summary={SUMMARY} />);
    expect(screen.getByText("5")).toBeTruthy();
    expect(screen.getByText("reviewed")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("newly mastered")).toBeTruthy();
    expect(screen.getByText("1")).toBeTruthy();
    expect(screen.getByText("still fuzzy")).toBeTruthy();
    expect(screen.getByText("7")).toBeTruthy();
    expect(screen.getByText("day streak")).toBeTruthy();
  });

  it("deep-links what to gulp next to Today (due) and Inbox", () => {
    render(<SessionSummary summary={SUMMARY} />);
    const dueLink = screen.getByRole("link", { name: /7 cards due tomorrow/i });
    expect(dueLink.getAttribute("href")).toBe("/");
    const inboxLink = screen.getByRole("link", { name: /4 items waiting in your inbox/i });
    expect(inboxLink.getAttribute("href")).toBe("/inbox");
  });

  it("keeps the back-to-today link", () => {
    render(<SessionSummary summary={SUMMARY} />);
    const backLink = screen.getByRole("link", { name: /back to today/i });
    expect(backLink.getAttribute("href")).toBe("/");
  });

  it("singularizes next-up counts of 1", () => {
    render(
      <SessionSummary
        summary={{ ...SUMMARY, next_up: { due_count: 1, inbox_count: 1 } }}
      />,
    );
    expect(screen.getByRole("link", { name: /1 card due tomorrow/i })).toBeTruthy();
    expect(
      screen.getByRole("link", { name: /1 item waiting in your inbox/i }),
    ).toBeTruthy();
  });
});
