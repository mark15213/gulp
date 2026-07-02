import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import { CardsView } from "./CardsView";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return {
    ...actual,
    getCards: vi.fn(),
    generateCards: vi.fn(),
    importCards: vi.fn(),
    updateCard: vi.fn(),
    deleteCard: vi.fn(),
    getSnapshot: vi.fn(),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const getCardsMock = () => api.getCards as ReturnType<typeof vi.fn>;
const generateMock = () => api.generateCards as ReturnType<typeof vi.fn>;
const importMock = () => api.importCards as ReturnType<typeof vi.fn>;
const updateMock = () => api.updateCard as ReturnType<typeof vi.fn>;
const deleteMock = () => api.deleteCard as ReturnType<typeof vi.fn>;
const getSnapshotMock = () => api.getSnapshot as ReturnType<typeof vi.fn>;

function card(overrides: Partial<api.CardOut> = {}): api.CardOut {
  return {
    id: "c1",
    card_type: "flashcard",
    prompt: "What objective does BERT use?",
    answer: "Masked LM",
    explanation: "From the report.",
    options: null,
    origin: "pack",
    status: "draft",
    created_at: "",
    updated_at: "",
    ...overrides,
  } as api.CardOut;
}

describe("CardsView", () => {
  it("loads and renders the source's cards with provenance", async () => {
    getCardsMock().mockResolvedValue([
      card(),
      card({ id: "c2", prompt: "Imported Q?", origin: "imported" }),
    ]);
    render(<CardsView snapshotId="s1" initialCardsStatus={null} />);
    expect(await screen.findByText("What objective does BERT use?")).toBeTruthy();
    expect(screen.getByText("Imported Q?")).toBeTruthy();
    expect(screen.getByText("AI")).toBeTruthy();
    expect(screen.getByText("Imported")).toBeTruthy();
  });

  it("accepts a draft card via updateCard", async () => {
    getCardsMock().mockResolvedValue([card()]);
    updateMock().mockResolvedValue(card({ status: "accepted" }));
    render(<CardsView snapshotId="s1" initialCardsStatus={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Accept" }));
    expect(updateMock()).toHaveBeenCalledWith("s1", "c1", { status: "accepted" });
  });

  it("rolls back and shows an error when accept fails", async () => {
    getCardsMock().mockResolvedValue([card()]);
    updateMock().mockRejectedValue(new Error("boom"));
    render(<CardsView snapshotId="s1" initialCardsStatus={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Accept" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy(); // still draft
  });

  it("generates: triggers the job, polls, and refetches cards when ready", async () => {
    getCardsMock().mockResolvedValueOnce([]);
    generateMock().mockResolvedValue({ cards_status: "generating" });
    getSnapshotMock().mockResolvedValue({ cards_status: "ready" });
    getCardsMock().mockResolvedValueOnce([card({ prompt: "Fresh card?" })]);
    render(<CardsView snapshotId="s1" initialCardsStatus={null} pollMs={5} />);
    await userEvent.click(await screen.findByRole("button", { name: "Generate cards" }));
    expect(generateMock()).toHaveBeenCalledWith("s1");
    expect(await screen.findByText("Fresh card?")).toBeTruthy();
  });

  it("shows a retryable error when generation fails", async () => {
    getCardsMock().mockResolvedValue([]);
    generateMock().mockResolvedValue({ cards_status: "generating" });
    getSnapshotMock().mockResolvedValue({ cards_status: "failed" });
    render(<CardsView snapshotId="s1" initialCardsStatus={null} pollMs={5} />);
    await userEvent.click(await screen.findByRole("button", { name: "Generate cards" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Generate cards" })).toBeTruthy(); // re-enabled
  });

  it("imports pasted cards.json and appends the result", async () => {
    getCardsMock().mockResolvedValue([]);
    importMock().mockResolvedValue([card({ id: "i1", prompt: "From NotebookLM?", origin: "imported" })]);
    render(<CardsView snapshotId="s1" initialCardsStatus={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Import cards" }));
    const box = await screen.findByLabelText("Paste cards.json");
    await userEvent.click(box);
    await userEvent.paste(JSON.stringify({ cards: [{ card_type: "flashcard", prompt: "From NotebookLM?", answer: "a" }] }));
    await userEvent.click(screen.getByRole("button", { name: "Import" }));
    await waitFor(() => expect(importMock()).toHaveBeenCalled());
    expect(await screen.findByText("From NotebookLM?")).toBeTruthy();
  });

  it("rejects unparseable import JSON client-side", async () => {
    getCardsMock().mockResolvedValue([]);
    render(<CardsView snapshotId="s1" initialCardsStatus={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Import cards" }));
    const box = await screen.findByLabelText("Paste cards.json");
    await userEvent.click(box);
    await userEvent.paste("not json");
    await userEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(importMock()).not.toHaveBeenCalled();
  });

  it("deletes a card", async () => {
    getCardsMock().mockResolvedValue([card()]);
    deleteMock().mockResolvedValue(undefined);
    render(<CardsView snapshotId="s1" initialCardsStatus={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(deleteMock()).toHaveBeenCalledWith("s1", "c1");
    await waitFor(() =>
      expect(screen.queryByText("What objective does BERT use?")).toBeNull(),
    );
  });
});
