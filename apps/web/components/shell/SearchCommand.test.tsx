import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { SearchCommand } from "./SearchCommand";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@gulp/api-client", () => ({
  getInbox: vi.fn().mockResolvedValue({ items: [], count: 0 }),
  getLibrary: vi.fn().mockResolvedValue({
    items: [{ id: "s1", title: "The Bitter Lesson", tags: ["ai"] }],
    count: 1,
  }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SearchCommand", () => {
  it("opens on click, filters, and navigates on Enter", async () => {
    render(<SearchCommand />);
    fireEvent.click(screen.getByRole("button", { name: /search/i }));
    const input = await screen.findByPlaceholderText(/search/i);
    fireEvent.change(input, { target: { value: "bitter" } });
    await screen.findByText("The Bitter Lesson");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(push).toHaveBeenCalledWith("/snapshots/s1");
  });

  it("opens with ⌘K and closes with Escape", () => {
    render(<SearchCommand />);
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(screen.getByRole("dialog", { name: "Search" })).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Search" })).toBeNull();
  });
});
