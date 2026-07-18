import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TokensSettings } from "./TokensSettings";

const getTokens = vi.fn();
const createToken = vi.fn();
const revokeToken = vi.fn();

vi.mock("@gulp/api-client", () => ({
  getTokens: (...a: unknown[]) => getTokens(...a),
  createToken: (...a: unknown[]) => createToken(...a),
  revokeToken: (...a: unknown[]) => revokeToken(...a),
}));

const TOKEN = {
  id: "t1",
  name: "laptop",
  prefix: "gulp_pat_abc12345",
  created_at: "2026-07-16T00:00:00Z",
  last_used_at: null,
};

beforeEach(() => {
  getTokens.mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("TokensSettings", () => {
  it("lists tokens with prefix and never a full token", async () => {
    getTokens.mockResolvedValue([TOKEN]);
    render(<TokensSettings />);
    expect(await screen.findByText("laptop")).toBeTruthy();
    expect(screen.getByText(/gulp_pat_abc12345/)).toBeTruthy();
  });

  it("creates a token and shows the plaintext once", async () => {
    getTokens.mockResolvedValue([]);
    createToken.mockResolvedValue({ ...TOKEN, token: "gulp_pat_abc12345FULL" });
    render(<TokensSettings />);
    fireEvent.change(await screen.findByPlaceholderText(/token name/i), {
      target: { value: "laptop" },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate/i }));
    expect(await screen.findByText(/gulp_pat_abc12345FULL/)).toBeTruthy();
    expect(createToken).toHaveBeenCalledWith("laptop");
  });

  it("revokes a token", async () => {
    getTokens.mockResolvedValue([TOKEN]);
    revokeToken.mockResolvedValue(undefined);
    render(<TokensSettings />);
    fireEvent.click(await screen.findByRole("button", { name: /revoke/i }));
    await waitFor(() => expect(revokeToken).toHaveBeenCalledWith("t1"));
  });
});
