import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import { ReaderToggle } from "./ReaderToggle";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, getCards: vi.fn() };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const PACK = {
  snapshot_id: "s1",
  status: "ready",
  title: "T",
  core_contributions: ["c"],
  key_insight: "k",
  sections: [],
  references: [],
} as unknown as api.PackOut;

describe("ReaderToggle", () => {
  it("switches to the Cards view", async () => {
    (api.getCards as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    render(
      <ReaderToggle pack={PACK} original={null} snapshotId="s1" cardsStatus={null} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Cards" }));
    expect(await screen.findByRole("button", { name: "Generate cards" })).toBeTruthy();
  });
});
