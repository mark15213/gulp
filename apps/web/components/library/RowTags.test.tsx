import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RowTags } from "./RowTags";

const addSnapshotTag = vi.fn().mockResolvedValue({});
const removeSnapshotTag = vi.fn().mockResolvedValue({});
vi.mock("@gulp/api-client", () => ({
  addSnapshotTag: (...a: unknown[]) => addSnapshotTag(...a),
  removeSnapshotTag: (...a: unknown[]) => removeSnapshotTag(...a),
}));

afterEach(() => {
  cleanup();
  addSnapshotTag.mockClear();
  removeSnapshotTag.mockClear();
});

describe("RowTags", () => {
  it("renders the source chip and filters on click", async () => {
    const onSourceClick = vi.fn();
    render(
      <RowTags
        snapshotId="s1"
        sourceFeed={{ id: "f1", title: "HF Paper Daily" }}
        tags={[]}
        onTagsChange={() => {}}
        onSourceClick={onSourceClick}
      />,
    );
    await userEvent.click(screen.getByText("HF Paper Daily"));
    expect(onSourceClick).toHaveBeenCalledWith("HF Paper Daily");
  });

  it("removes a tag optimistically and calls the API", async () => {
    const onTagsChange = vi.fn();
    render(
      <RowTags snapshotId="s1" sourceFeed={null} tags={["pretrain"]} onTagsChange={onTagsChange} onSourceClick={() => {}} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Remove tag pretrain" }));
    expect(onTagsChange).toHaveBeenCalledWith([]);
    await waitFor(() => expect(removeSnapshotTag).toHaveBeenCalledWith("s1", "pretrain"));
  });

  it("adds a tag via the + control", async () => {
    const onTagsChange = vi.fn();
    render(
      <RowTags snapshotId="s1" sourceFeed={null} tags={[]} onTagsChange={onTagsChange} onSourceClick={() => {}} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Add tag" }));
    await userEvent.type(screen.getByPlaceholderText("tag"), "rl{Enter}");
    expect(onTagsChange).toHaveBeenCalledWith(["rl"]);
    await waitFor(() => expect(addSnapshotTag).toHaveBeenCalledWith("s1", "rl"));
  });
});
