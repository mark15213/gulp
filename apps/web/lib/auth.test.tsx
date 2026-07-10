import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { UserPublic } from "@gulp/api-client";
import { AuthProvider, useAuth } from "./auth";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, logout: vi.fn() };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function Probe() {
  const { user } = useAuth();
  return <span>{user ? user.email : "anon"}</span>;
}

describe("AuthProvider", () => {
  it("exposes the initial user", () => {
    const u: UserPublic = {
      id: "1",
      email: "me@example.com",
      display_name: "Me",
      locale: "en",
      gulp_session_minutes: 5,
      created_at: "",
    };
    render(
      <AuthProvider initialUser={u}>
        <Probe />
      </AuthProvider>,
    );
    expect(screen.getByText("me@example.com")).toBeTruthy();
  });
});
