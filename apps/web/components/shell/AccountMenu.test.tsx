import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccountMenu } from "./AccountMenu";

const signOut = vi.fn();
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { email: "me@example.com", display_name: "Me" },
    signOut,
  }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AccountMenu", () => {
  it("shows the user and logs out", async () => {
    render(<AccountMenu />);
    expect(screen.getByText("me@example.com")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(signOut).toHaveBeenCalled();
  });
});
