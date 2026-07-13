import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import type { GulpSession, SessionCard } from "@gulp/api-client";
import { SessionRunner } from "./SessionRunner";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return {
    ...actual,
    reviewCard: vi.fn(),
    snoozeCard: vi.fn(),
    completeGulpSession: vi.fn(),
  };
});

const reviewCardMock = () => api.reviewCard as ReturnType<typeof vi.fn>;
const snoozeCardMock = () => api.snoozeCard as ReturnType<typeof vi.fn>;
const completeMock = () => api.completeGulpSession as ReturnType<typeof vi.fn>;

function card(
  id: string,
  prompt: string,
  reason: SessionCard["reason"] = "due",
): SessionCard {
  return {
    id,
    card_type: "flashcard",
    prompt,
    answer: `answer-${id}`,
    explanation: null,
    source_title: "Attention Is All You Need",
    reason,
    daily: "learning",
  };
}

function session(cards: SessionCard[]): GulpSession {
  return {
    id: "sess-1",
    scope_type: "daily",
    target_minutes: 5,
    status: "active",
    started_at: null,
    cards,
  };
}

const SUMMARY = {
  reviewed_count: 3,
  newly_mastered: 1,
  still_fuzzy: 0,
  streak_days: 4,
  next_up: { due_count: 2, inbox_count: 1 },
};

async function revealAndGrade(gradeName: RegExp) {
  await userEvent.click(screen.getByRole("button", { name: /show answer/i }));
  await userEvent.click(screen.getByRole("button", { name: gradeName }));
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SessionRunner — retest queue (Task 17 fix)", () => {
  it("shows the current card position in the progress header", () => {
    render(
      <SessionRunner
        initial={session([card("c1", "Prompt one"), card("c2", "Prompt two")])}
      />,
    );

    expect(screen.getByText("1 / 2")).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
      "1",
    );
  });

  it("does not duplicate cards when the server's next_card echoes what's already queued", async () => {
    // This is exactly the bug: the server hands back the next PLANNED card
    // (already sitting in our own queue) on every review — the old code
    // appended it, duplicating c2/c3. The fix must ignore it entirely.
    const c1 = card("c1", "Prompt one");
    const c2 = card("c2", "Prompt two");
    const c3 = card("c3", "Prompt three");
    reviewCardMock().mockImplementation(
      (_sessionId: string, body: { card_id: string }) => {
        const echoed =
          body.card_id === "c1" ? c2 : body.card_id === "c2" ? c3 : null;
        return Promise.resolve({ mastery: {}, next_card: echoed, done: false });
      },
    );
    completeMock().mockResolvedValue(SUMMARY);

    render(<SessionRunner initial={session([c1, c2, c3])} />);

    expect(screen.getByText("Prompt one")).toBeTruthy();
    await revealAndGrade(/got it/i);

    await waitFor(() => expect(screen.getByText("Prompt two")).toBeTruthy());
    await revealAndGrade(/got it/i);

    await waitFor(() => expect(screen.getByText("Prompt three")).toBeTruthy());
    await revealAndGrade(/got it/i);

    // Exactly 3 grades were submitted and the session completed — no
    // duplicated 4th/5th pass through c2/c3.
    await waitFor(() => expect(completeMock()).toHaveBeenCalledTimes(1));
    expect(reviewCardMock()).toHaveBeenCalledTimes(3);
    expect(await screen.findByText("Session complete")).toBeTruthy();
  });

  it("requeues a missed card for exactly one retest, never twice (no infinite loop)", async () => {
    const c1 = card("c1", "Prompt one");
    const c2 = card("c2", "Prompt two");
    reviewCardMock().mockResolvedValue({
      mastery: {},
      next_card: null,
      done: false,
    });
    completeMock().mockResolvedValue(SUMMARY);

    render(<SessionRunner initial={session([c1, c2])} />);

    // Miss c1 — it goes to the back of the queue for one retest.
    expect(screen.getByText("Prompt one")).toBeTruthy();
    await revealAndGrade(/missed/i);

    // c2 comes up next (not the retest yet).
    await waitFor(() => expect(screen.getByText("Prompt two")).toBeTruthy());
    await revealAndGrade(/got it/i);

    // c1's retest pass.
    await waitFor(() => expect(screen.getByText("Prompt one")).toBeTruthy());
    expect(screen.getByText(/· retest/)).toBeTruthy();

    // Miss it again — since it's already had its one retest, it must NOT be
    // requeued a second time (that would loop forever); the session ends.
    await revealAndGrade(/missed/i);

    await waitFor(() => expect(completeMock()).toHaveBeenCalledTimes(1));
    expect(reviewCardMock()).toHaveBeenCalledTimes(3);
    expect(await screen.findByText("Session complete")).toBeTruthy();
  });
});

describe("SessionRunner — snooze", () => {
  it("drops the card via snoozeCard, without grading or retesting it", async () => {
    const c1 = card("c1", "Prompt one");
    const c2 = card("c2", "Prompt two");
    snoozeCardMock().mockResolvedValue({
      mastery: {},
      next_card: null,
      done: false,
    });
    completeMock().mockResolvedValue(SUMMARY);

    render(<SessionRunner initial={session([c1, c2])} />);

    await userEvent.click(screen.getByRole("button", { name: /show answer/i }));
    await userEvent.click(
      screen.getByRole("button", { name: /snooze.*bring it back tomorrow/i }),
    );

    expect(snoozeCardMock()).toHaveBeenCalledWith("sess-1", "c1");
    expect(reviewCardMock()).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByText("Prompt two")).toBeTruthy());
  });
});
