import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "./ChatPanel";

const getPackMessages = vi.fn().mockResolvedValue([]);
const postPackMessage = vi.fn().mockResolvedValue({
  id: "a1", role: "assistant", content: "Answer.", block_refs: [], created_at: "",
});
vi.mock("@gulp/api-client", () => ({
  getPackMessages: (...a: unknown[]) => getPackMessages(...a),
  postPackMessage: (...a: unknown[]) => postPackMessage(...a),
}));

afterEach(() => { cleanup(); getPackMessages.mockClear(); postPackMessage.mockClear(); });

describe("ChatPanel", () => {
  it("renders attachment chips and removes them", async () => {
    const onRemove = vi.fn();
    render(
      <ChatPanel snapshotId="s1" attachments={[{ id: "b1", label: "para" }]}
        onRemoveAttachment={onRemove} onClose={() => {}} />,
    );
    expect(screen.getByText("para")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Remove para" }));
    expect(onRemove).toHaveBeenCalledWith("b1");
  });

  it("sends with the attached block_refs", async () => {
    render(
      <ChatPanel snapshotId="s1" attachments={[{ id: "b1", label: "para" }]}
        onRemoveAttachment={() => {}} onClose={() => {}} />,
    );
    await userEvent.type(screen.getByRole("textbox"), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(postPackMessage).toHaveBeenCalledWith("s1", { content: "hello", block_refs: ["b1"] }),
    );
  });
});
