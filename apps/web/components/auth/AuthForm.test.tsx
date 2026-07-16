import React from "react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import { AuthForm } from "./AuthForm";

const router = vi.hoisted(() => ({
  replace: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, login: vi.fn(), register: vi.fn() };
});
vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ setUser: vi.fn() }) }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AuthForm", () => {
  it("submits login credentials", async () => {
    (api.login as Mock).mockResolvedValue({ email: "me@example.com" });
    render(<AuthForm mode="login" />);
    await userEvent.type(screen.getByLabelText("Email"), "me@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter2hunter");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(api.login).toHaveBeenCalledWith({
      email: "me@example.com",
      password: "hunter2hunter",
    });
    expect(router.replace).toHaveBeenCalledWith("/");
    expect(router.refresh).toHaveBeenCalledTimes(1);
  });

  it("passes the invite code when registering", async () => {
    (api.register as Mock).mockResolvedValue({ email: "a@b.com" });
    render(<AuthForm mode="register" />);
    await userEvent.type(screen.getByLabelText("Email"), "a@b.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter2hunter");
    await userEvent.type(screen.getByLabelText("Invite code"), "5566");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(api.register).toHaveBeenCalledWith({
      email: "a@b.com",
      password: "hunter2hunter",
      locale: "en",
      invite_code: "5566",
    });
  });

  it("surfaces an error on failure", async () => {
    (api.login as Mock).mockRejectedValue(new Error("bad"));
    render(<AuthForm mode="login" />);
    await userEvent.type(screen.getByLabelText("Email"), "me@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter2hunter");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(screen.getByRole("alert")).toBeTruthy();
  });
});
