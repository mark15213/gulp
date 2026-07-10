import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import { ReaderToggle } from "./ReaderToggle";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, getCards: vi.fn(), getFigures: vi.fn(async () => []) };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const PACK = {
  snapshot_id: "s1",
  status: "ready",
  pack_type: "article",
  title: "T",
  summary: null,
  core_contributions: [],
  key_insight: null,
  sections: [],
  references: [],
} as unknown as api.PackOut;

describe("ReaderToggle", () => {
  it("shows Pack and Cards tabs but not Original", () => {
    render(<ReaderToggle pack={PACK} snapshotId="s1" cardsStatus={null} />);
    expect(
      screen.getByRole("button", { name: "Pack" }).getAttribute("aria-pressed"),
    ).toBe("true");
    expect(
      screen
        .getByRole("button", { name: "Cards" })
        .getAttribute("aria-pressed"),
    ).toBe("false");
    expect(screen.queryByRole("button", { name: "Original" })).toBeNull();
  });

  it("switches to the Cards view", async () => {
    (api.getCards as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    render(<ReaderToggle pack={PACK} snapshotId="s1" cardsStatus={null} />);
    await userEvent.click(screen.getByRole("button", { name: "Cards" }));
    expect(
      screen
        .getByRole("button", { name: "Cards" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(
      await screen.findByRole("button", { name: "Generate cards" }),
    ).toBeTruthy();
  });
});
