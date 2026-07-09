import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SidebarNav, isActive } from "./SidebarNav";

const usePathname = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ usePathname }));

afterEach(() => cleanup());

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
  it("marks the current route with aria-current", () => {
    usePathname.mockReturnValue("/inbox");
    render(<SidebarNav inboxCount={2} />);
    const current = screen.getByRole("link", { current: "page" });
    expect(current.textContent).toContain("Inbox");
    expect(screen.getByText("2")).toBeTruthy();
  });

  it("marks nothing on snapshot detail pages", () => {
    usePathname.mockReturnValue("/snapshots/abc");
    render(<SidebarNav inboxCount={0} />);
    expect(screen.queryByRole("link", { current: "page" })).toBeNull();
  });

  it("lights Feeds on its subtree", () => {
    usePathname.mockReturnValue("/feeds/discover");
    render(<SidebarNav inboxCount={0} />);
    const current = screen.getByRole("link", { current: "page" });
    expect(current.textContent).toContain("Feeds");
  });
});
