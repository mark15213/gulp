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
const getPackMessages = vi.fn();
const postPackMessage = vi.fn();
vi.mock("@gulp/api-client", () => ({
  getPackMessages: (...a: unknown[]) => getPackMessages(...a),
  postPackMessage: (...a: unknown[]) => postPackMessage(...a),
}));

beforeEach(() => {
  getPackMessages.mockReset();
  getPackMessages.mockResolvedValue([]);
  postPackMessage.mockReset();
  postPackMessage.mockResolvedValue(ANSWER);
});

afterEach(cleanup);

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

  it("sends with the attached block_refs", async () => {
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[{ id: "b1", label: "para" }]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    await screen.findByText("Start a conversation");
    await userEvent.type(screen.getByRole("textbox"), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(postPackMessage).toHaveBeenCalledWith("s1", {
        content: "hello",
        block_refs: ["b1"],
      }),
    );
  });

  it("sends with Ctrl+Enter", async () => {
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    await screen.findByText("Start a conversation");
    await userEvent.type(
      screen.getByRole("textbox"),
      "hello{Control>}{Enter}{/Control}",
    );
    await waitFor(() =>
      expect(postPackMessage).toHaveBeenCalledWith("s1", {
        content: "hello",
        block_refs: [],
      }),
    );
  });

  it("rolls back an optimistic message and restores the draft after a send error", async () => {
    postPackMessage.mockRejectedValueOnce(new Error("nope"));
    render(
      <ChatPanel
        snapshotId="s1"
        attachments={[]}
        onRemoveAttachment={() => {}}
        onClose={() => {}}
      />,
    );
    await screen.findByText("Start a conversation");
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
