import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import * as api from "@gulp/api-client";
import { SidebarNav, isActive } from "./SidebarNav";

const usePathname = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ usePathname }));

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, getInbox: vi.fn() };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("isActive", () => {
  it("matches Today only on the exact root", () => {
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/inbox", "/")).toBe(false);
  });

  it("prefix-matches sections", () => {
    expect(isActive("/inbox", "/inbox")).toBe(true);
    expect(isActive("/library/x", "/library")).toBe(true);
    expect(isActive("/librarian", "/library")).toBe(false);
    expect(isActive("/snapshots/abc", "/inbox")).toBe(false);
  });
});

describe("SidebarNav", () => {
  it("reconciles a stale server badge with the latest inbox count", async () => {
    usePathname.mockReturnValue("/inbox");
    (api.getInbox as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      count: 0,
    });

    render(<SidebarNav inboxCount={1} />);
    expect(screen.getByText("1")).toBeTruthy();

    await waitFor(() => expect(screen.queryByText("1")).toBeNull());
  });

  it("rechecks the count after a client-side route change", async () => {
    usePathname.mockReturnValue("/feeds");
    (api.getInbox as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ items: [], count: 2 })
      .mockResolvedValueOnce({ items: [], count: 0 });

    const view = render(<SidebarNav inboxCount={2} />);
    await waitFor(() => expect(api.getInbox).toHaveBeenCalledTimes(1));

    usePathname.mockReturnValue("/inbox");
    view.rerender(<SidebarNav inboxCount={2} />);

    await waitFor(() => expect(screen.queryByText("2")).toBeNull());
    expect(api.getInbox).toHaveBeenCalledTimes(2);
  });

  it("uses a new server count immediately while reconciling in the background", () => {
    usePathname.mockReturnValue("/inbox");
    (api.getInbox as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {}),
    );

    const view = render(<SidebarNav inboxCount={1} />);
    expect(screen.getByText("1")).toBeTruthy();

    view.rerender(<SidebarNav inboxCount={0} />);
    expect(screen.queryByText("1")).toBeNull();
  });

  it("keeps the server count when background reconciliation fails", async () => {
    usePathname.mockReturnValue("/inbox");
    (api.getInbox as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("offline"),
    );

    render(<SidebarNav inboxCount={1} />);

    await waitFor(() => expect(api.getInbox).toHaveBeenCalledTimes(1));
    expect(screen.getByText("1")).toBeTruthy();
  });

  it("marks the current route with aria-current", () => {
    usePathname.mockReturnValue("/inbox");
    (api.getInbox as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {}),
    );
    render(<SidebarNav inboxCount={2} />);
    const current = screen.getByRole("link", { current: "page" });
    expect(current.textContent).toContain("Inbox");
    expect(screen.getByText("2")).toBeTruthy();
  });

  it("marks nothing on snapshot detail pages", () => {
    usePathname.mockReturnValue("/snapshots/abc");
    (api.getInbox as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {}),
    );
    render(<SidebarNav inboxCount={0} />);
    expect(screen.queryByRole("link", { current: "page" })).toBeNull();
  });

  it("lights Feeds on its subtree", () => {
    usePathname.mockReturnValue("/feeds/discover");
    (api.getInbox as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {}),
    );
    render(<SidebarNav inboxCount={0} />);
    const current = screen.getByRole("link", { current: "page" });
    expect(current.textContent).toContain("Feeds");
  });
});
