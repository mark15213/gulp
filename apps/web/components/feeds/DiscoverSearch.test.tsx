import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { DiscoverSearch } from "./DiscoverSearch";

const { searchCatalog } = vi.hoisted(() => ({
  searchCatalog: vi.fn(),
}));

vi.mock("@gulp/api-client", () => ({
  createSubscription: vi.fn(),
  searchCatalog,
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const route = (routePath: string) => ({
  namespace: "example",
  namespace_name: "Example",
  route_path: routePath,
  route_name: `Route ${routePath}`,
  example: null,
  parameters: null,
  require_config: false,
  heat: 1,
});

describe("DiscoverSearch", () => {
  it("pages through all catalog matches using the searched query", async () => {
    searchCatalog
      .mockResolvedValueOnce({ items: [route("/first")], count: 30 })
      .mockResolvedValueOnce({ items: [route("/second")], count: 30 });

    render(<DiscoverSearch />);
    fireEvent.change(
      screen.getByPlaceholderText(/Search the RSSHub catalog/),
      { target: { value: "papers" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("Page 1 of 2")).toBeDefined();
    expect(searchCatalog).toHaveBeenNthCalledWith(1, "papers", 24, 0);
    expect(screen.getByText("Catalog · 30 routes")).toBeDefined();
    expect(
      screen.getByRole("button", { name: "Previous" }).hasAttribute("disabled"),
    ).toBe(true);

    // Editing the input does not change the query behind the current result set.
    fireEvent.change(
      screen.getByPlaceholderText(/Search the RSSHub catalog/),
      { target: { value: "edited" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(searchCatalog).toHaveBeenNthCalledWith(2, "papers", 24, 24);
    });
    expect(await screen.findByText("Page 2 of 2")).toBeDefined();
    expect(screen.getByText("Route /second")).toBeDefined();
    expect(
      screen.getByRole("button", { name: "Next" }).hasAttribute("disabled"),
    ).toBe(true);
  });

  it("shows a single disabled page for no matches", async () => {
    searchCatalog.mockResolvedValueOnce({ items: [], count: 0 });

    render(<DiscoverSearch />);
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("Catalog · no matches")).toBeDefined();
    expect(screen.getByText("Page 1 of 1")).toBeDefined();
    expect(
      screen.getByRole("button", { name: "Previous" }).hasAttribute("disabled"),
    ).toBe(true);
    expect(
      screen.getByRole("button", { name: "Next" }).hasAttribute("disabled"),
    ).toBe(true);
  });
});
