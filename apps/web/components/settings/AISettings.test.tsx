import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AISettings } from "./AISettings";

const settings = {
  default_provider: null as string | null,
  default_model: null as string | null,
  credentials: [] as { provider: string; masked_key: string }[],
  catalog: [
    {
      provider: "anthropic",
      capabilities: ["json", "stream", "tools", "vision"],
      models: [{ id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" }],
    },
    {
      provider: "deepseek",
      capabilities: ["json", "stream", "tools"],
      models: [{ id: "deepseek-chat", label: "DeepSeek Chat" }],
    },
  ],
};

const getLLMSettings = vi.fn();
const putLLMCredential = vi.fn();
const deleteLLMCredential = vi.fn();

vi.mock("@gulp/api-client", () => ({
  getLLMSettings: (...a: unknown[]) => getLLMSettings(...a),
  putLLMCredential: (...a: unknown[]) => putLLMCredential(...a),
  deleteLLMCredential: (...a: unknown[]) => deleteLLMCredential(...a),
}));

beforeEach(() => {
  getLLMSettings.mockResolvedValue(structuredClone(settings));
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AISettings", () => {
  it("renders a card per catalog provider", async () => {
    render(<AISettings />);
    expect(await screen.findByText("Anthropic")).toBeTruthy();
    expect(screen.getByText("DeepSeek")).toBeTruthy();
  });

  it("saves a key then refreshes", async () => {
    putLLMCredential.mockResolvedValue(undefined);
    render(<AISettings />);
    const card = (await screen.findByText("DeepSeek")).closest("section");
    expect(card).toBeTruthy();
    const scoped = within(card as HTMLElement);
    await userEvent.type(scoped.getByPlaceholderText("API key"), "sk-x");
    await userEvent.click(scoped.getByRole("button", { name: "Save key" }));
    await waitFor(() =>
      expect(putLLMCredential).toHaveBeenCalledWith("deepseek", "sk-x"),
    );
    expect(getLLMSettings).toHaveBeenCalledTimes(2);
  });

  it("shows masked key + delete for configured providers", async () => {
    getLLMSettings.mockResolvedValue({
      ...structuredClone(settings),
      credentials: [{ provider: "deepseek", masked_key: "…3456" }],
    });
    render(<AISettings />);
    expect(await screen.findByText("…3456")).toBeTruthy();
    const card = screen
      .getByRole("heading", { name: "DeepSeek" })
      .closest("section");
    expect(
      within(card as HTMLElement).getByRole("button", { name: "Delete key" }),
    ).toBeTruthy();
  });

  it("surfaces a rejected key", async () => {
    putLLMCredential.mockRejectedValue(new Error("invalid_key"));
    render(<AISettings />);
    const card = (await screen.findByText("DeepSeek")).closest("section");
    const scoped = within(card as HTMLElement);
    await userEvent.type(scoped.getByPlaceholderText("API key"), "sk-bad");
    await userEvent.click(scoped.getByRole("button", { name: "Save key" }));
    expect(
      await screen.findByText("That key was rejected by the provider."),
    ).toBeTruthy();
  });

  it("keeps model choice out of settings", async () => {
    render(<AISettings />);
    expect(
      await screen.findByRole("heading", { name: "AI providers" }),
    ).toBeTruthy();
    expect(
      screen.getByText(/Choose the model directly in each chat/),
    ).toBeTruthy();
    expect(screen.queryByLabelText("Default model")).toBeNull();
  });
});
