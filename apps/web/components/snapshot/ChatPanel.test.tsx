import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "./ChatPanel";

const ANSWER = {
  id: "a1",
  role: "assistant",
  content: "Answer.",
  block_refs: [],
  created_at: "",
};
const LLM_SETTINGS = {
  default_provider: "anthropic",
  default_model: "claude-sonnet-4-6",
  credentials: [
    { provider: "anthropic", masked_key: "…1111" },
    { provider: "deepseek", masked_key: "…2222" },
  ],
  catalog: [
    {
      provider: "anthropic",
      capabilities: ["stream"],
      models: [{ id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" }],
    },
    {
      provider: "deepseek",
      capabilities: ["stream"],
      models: [
        { id: "deepseek-chat", label: "DeepSeek Chat" },
        { id: "deepseek-reasoner", label: "DeepSeek Reasoner" },
      ],
    },
  ],
};
const DEFAULT_MODEL = {
  provider: "anthropic",
  model: "claude-sonnet-4-6",
};
const getPackMessages = vi.fn();
const getLLMSettings = vi.fn();
const streamPackMessage = vi.fn();
vi.mock("@gulp/api-client", () => ({
  getPackMessages: (...a: unknown[]) => getPackMessages(...a),
  getLLMSettings: (...a: unknown[]) => getLLMSettings(...a),
  streamPackMessage: (...a: unknown[]) => streamPackMessage(...a),
}));

function stream(events: unknown[]) {
  return (async function* () {
    for (const e of events) yield e;
  })();
}

beforeEach(() => {
  localStorage.clear();
  getPackMessages.mockReset();
  getPackMessages.mockResolvedValue([]);
  getLLMSettings.mockReset();
  getLLMSettings.mockResolvedValue(structuredClone(LLM_SETTINGS));
  streamPackMessage.mockReset();
  streamPackMessage.mockImplementation(() =>
    stream([
      { type: "delta", text: "Answer." },
      { type: "done", message: ANSWER },
    ]),
  );
});

afterEach(cleanup);

async function waitForChatReady() {
  await screen.findByText("Start a conversation");
  const select = screen.getByRole("combobox", {
    name: "AI model",
  }) as HTMLSelectElement;
  await waitFor(() => expect(select.value).toBe("anthropic:claude-sonnet-4-6"));
}

describe("ChatPanel", () => {
  it("shows a loading state while the conversation is being fetched", () => {
    getPackMessages.mockImplementationOnce(() => new Promise(() => {}));
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.getByRole("status").textContent).toContain(
      "Loading conversation…",
    );
    expect(screen.queryByText("Start a conversation")).toBeNull();
  });

  it("shows an empty state after an empty conversation loads", async () => {
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    expect(await screen.findByText("Start a conversation")).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "AI model" })).toBeTruthy();
  });

  it("selects the model in chat and sends that exact provider and model", async () => {
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    await waitForChatReady();
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "AI model" }),
      "deepseek:deepseek-reasoner",
    );
    await userEvent.type(screen.getByRole("textbox"), "compare this");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(streamPackMessage).toHaveBeenCalledWith("s1", {
        content: "compare this",
        block_refs: [],
        provider: "deepseek",
        model: "deepseek-reasoner",
      }),
    );
    expect(localStorage.getItem("chat:selectedModel")).toBe(
      "deepseek:deepseek-reasoner",
    );
  });

  it("points to provider settings and disables chat when no key is configured", async () => {
    getLLMSettings.mockResolvedValueOnce({
      ...structuredClone(LLM_SETTINGS),
      default_provider: null,
      default_model: null,
      credentials: [],
    });
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    const setup = await screen.findByRole("link", {
      name: "Settings → AI providers",
    });
    expect(setup.getAttribute("href")).toBe("/settings/ai");
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).disabled).toBe(
      true,
    );
  });

  it("closes the panel from the header", async () => {
    const onClose = vi.fn();
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={onClose}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Close chat" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders load errors inside the conversation region", async () => {
    getPackMessages.mockRejectedValueOnce(new Error("nope"));
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    const error = await screen.findByRole("alert");
    expect(error.textContent).toContain("Couldn't load the conversation.");
    expect(screen.getByRole("log").contains(error)).toBe(true);
  });

  it("renders attachment chips and removes them", async () => {
    const onRemove = vi.fn();
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[{ id: "b1", label: "para" }]}
        onRemoveAttachment={onRemove}
        onClose={() => {}}
      />,
    );
    expect(screen.getByText("para")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Remove para" }));
    expect(onRemove).toHaveBeenCalledWith("b1");
  });

  it("renders saved assistant answers as markdown and opens their article references", async () => {
    const onOpenReference = vi.fn();
    getPackMessages.mockResolvedValueOnce([
      { ...ANSWER, content: "**Bold answer**", block_refs: ["b1"] },
    ]);
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onOpenReference={onOpenReference}
        onClose={() => {}}
      />,
    );
    const answer = await screen.findByText("Bold answer");
    expect(answer.tagName).toBe("STRONG");
    await userEvent.click(screen.getByRole("button", { name: "Passage 1" }));
    expect(onOpenReference).toHaveBeenCalledWith("b1");
  });

  it("renders deltas incrementally then the final message", async () => {
    streamPackMessage.mockImplementation(() =>
      stream([
        { type: "delta", text: "Hel" },
        { type: "delta", text: "lo" },
        { type: "done", message: { ...ANSWER, content: "Hello" } },
      ]),
    );
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    await waitForChatReady();
    await userEvent.type(screen.getByRole("textbox"), "hi");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Hello")).toBeTruthy();
    expect(streamPackMessage).toHaveBeenCalledWith("s1", {
      content: "hi",
      block_refs: [],
      ...DEFAULT_MODEL,
    });
  });

  it("surfaces llm_not_configured with a settings pointer", async () => {
    streamPackMessage.mockImplementation(() =>
      stream([{ type: "error", code: "llm_not_configured" }]),
    );
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    await waitForChatReady();
    await userEvent.type(screen.getByRole("textbox"), "hi");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Settings → AI providers");
  });

  it("sends with the attached block_refs", async () => {
    const onClearAttachments = vi.fn();
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[{ id: "b1", label: "para" }]}
        onRemoveAttachment={() => {}}
        onClearAttachments={onClearAttachments}
        onClose={() => {}}
      />,
    );
    await waitForChatReady();
    await userEvent.type(screen.getByRole("textbox"), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(streamPackMessage).toHaveBeenCalledWith("s1", {
        content: "hello",
        block_refs: ["b1"],
        ...DEFAULT_MODEL,
      }),
    );
    await waitFor(() => expect(onClearAttachments).toHaveBeenCalledOnce());
  });

  it("sends with Enter", async () => {
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    await waitForChatReady();
    await userEvent.type(screen.getByRole("textbox"), "hello{Enter}");
    await waitFor(() =>
      expect(streamPackMessage).toHaveBeenCalledWith("s1", {
        content: "hello",
        block_refs: [],
        ...DEFAULT_MODEL,
      }),
    );
  });

  it("keeps Shift+Enter as a new line", async () => {
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    await waitForChatReady();
    const input = screen.getByRole("textbox") as HTMLTextAreaElement;
    await userEvent.type(input, "line one{Shift>}{Enter}{/Shift}line two");
    expect(streamPackMessage).not.toHaveBeenCalled();
    expect(input.value).toBe("line one\nline two");
  });

  it("closes with Escape", async () => {
    const onClose = vi.fn();
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={onClose}
      />,
    );
    await waitForChatReady();
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("rolls back an optimistic message and restores the draft after a send error", async () => {
    streamPackMessage.mockImplementationOnce(() => {
      throw new Error("nope");
    });
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    await waitForChatReady();
    const input = screen.getByRole("textbox") as HTMLTextAreaElement;
    await userEvent.type(input, "keep this question");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(input.value).toBe("keep this question");
    expect(screen.getByRole("log").textContent).not.toContain(
      "keep this question",
    );
  });
});
