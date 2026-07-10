import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import * as api from "@gulp/api-client";
import { Sidebar } from "./Sidebar";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, getInbox: vi.fn() };
});

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { email: "dev@gulp.local", display_name: "Dev" },
    signOut: vi.fn(),
  }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Sidebar", () => {
  it("nav is Today · Feeds · Inbox · Library, Today first, wired hrefs", async () => {
    (api.getInbox as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], count: 2 });
    render(await Sidebar());
    const nav = screen.getByRole("navigation", { name: "Primary" });
    const links = Array.from(nav.querySelectorAll("a"));
    expect(links.map((l) => l.textContent?.replace(/\d+$/, ""))).toEqual([
      "Today",
      "Feeds",
      "Inbox",
      "Library",
    ]);
    expect(links.map((l) => l.getAttribute("href"))).toEqual([
      "/",
      "/feeds",
      "/inbox",
      "/library",
    ]);
    expect(screen.getByText("2")).toBeTruthy(); // inbox to-do badge
  });
});
