import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SettingsLink } from "./SettingsLink";

let pathname = "/";
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
}));

afterEach(cleanup);

describe("SettingsLink", () => {
  it("links to /settings without active state elsewhere", () => {
    pathname = "/library";
    render(<SettingsLink />);
    const link = screen.getByRole("link", { name: /Settings/ });
    expect(link.getAttribute("href")).toBe("/settings");
    expect(link.getAttribute("aria-current")).toBeNull();
  });

  it("is active on the settings subtree", () => {
    pathname = "/settings/ai";
    render(<SettingsLink />);
    const link = screen.getByRole("link", { name: /Settings/ });
    expect(link.getAttribute("aria-current")).toBe("page");
  });
});
