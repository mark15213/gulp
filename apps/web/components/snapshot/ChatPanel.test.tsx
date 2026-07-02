import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import { ChatPanel } from "./ChatPanel";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, getBlockMessages: vi.fn(), postBlockMessage: vi.fn() };
});

afterEach(cleanup);

const getMock = () => api.getBlockMessages as ReturnType<typeof vi.fn>;
const postMock = () => api.postBlockMessage as ReturnType<typeof vi.fn>;

describe("ChatPanel", () => {
  it("loads and renders the block's conversation on open", async () => {
    getMock().mockResolvedValue([
      { id: "m1", role: "user", content: "Why masking?", created_at: "" },
      { id: "m2", role: "assistant", content: "Because bidirectionality.", created_at: "" },
    ]);
    render(<ChatPanel snapshotId="s1" blockId="b1" onClose={vi.fn()} />);
    expect(await screen.findByText("Because bidirectionality.")).toBeTruthy();
    expect(screen.getByText("Why masking?")).toBeTruthy();
    expect(getMock()).toHaveBeenCalledWith("s1", "b1");
  });

  it("sends a question and appends the assistant reply", async () => {
    getMock().mockResolvedValue([]);
    postMock().mockResolvedValue({ id: "a1", role: "assistant", content: "Grounded answer.", created_at: "" });
    render(<ChatPanel snapshotId="s1" blockId="b1" onClose={vi.fn()} />);
    const input = await screen.findByLabelText("Ask about this block");
    await userEvent.type(input, "What is it?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(postMock()).toHaveBeenCalledWith("s1", "b1", { content: "What is it?" });
    expect(await screen.findByText("Grounded answer.")).toBeTruthy();
    expect(screen.getByText("What is it?")).toBeTruthy(); // optimistic user bubble stays
  });

  it("close button calls onClose", async () => {
    getMock().mockResolvedValue([]);
    const onClose = vi.fn();
    render(<ChatPanel snapshotId="s1" blockId="b1" onClose={onClose} />);
    await userEvent.click(await screen.findByLabelText("Close chat"));
    expect(onClose).toHaveBeenCalled();
  });
});
