import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  pathname: vi.fn(),
  redirect: vi.fn((destination: string) => {
    throw new Error(`redirect:${destination}`);
  }),
}));

vi.mock("next/headers", () => ({
  headers: async () => ({ get: mocks.pathname }),
}));
vi.mock("next/navigation", () => ({
  redirect: mocks.redirect,
  usePathname: () => "/login",
  useRouter: () => ({ replace: vi.fn() }),
}));
vi.mock("@/lib/serverApi", () => ({
  getMe: mocks.getMe,
  getInbox: vi.fn(() => {
    throw new Error("public routes must not fetch the inbox");
  }),
}));

import { Shell } from "./Shell";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Shell authentication boundary", () => {
  it("renders a public route without resolving authenticated chrome", async () => {
    mocks.pathname.mockReturnValue("/login");
    mocks.getMe.mockResolvedValue(null);

    render(await Shell({ children: <div>Sign in</div> }));

    expect(screen.getByText("Sign in")).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
  });

  it("redirects an unauthenticated protected request to login", async () => {
    mocks.pathname.mockReturnValue("/inbox");
    mocks.getMe.mockResolvedValue(null);

    await expect(Shell({ children: <div>Inbox</div> })).rejects.toThrow(
      "redirect:/login",
    );
  });

  it("redirects an authenticated user away from auth pages", async () => {
    mocks.pathname.mockReturnValue("/login");
    mocks.getMe.mockResolvedValue({ id: "user-1" });

    await expect(Shell({ children: <div>Sign in</div> })).rejects.toThrow(
      "redirect:/",
    );
  });
});
