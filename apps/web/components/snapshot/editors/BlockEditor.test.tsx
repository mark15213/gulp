import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { PackBlockOut } from "@gulp/api-client";
import { BlockEditor } from "./BlockEditor";

afterEach(cleanup);

describe("BlockEditor", () => {
  it("renders the table editor for a table block", () => {
    const block: PackBlockOut = { id: "b", type: "table", headers: ["H"], rows: [["a"]], caption: null };
    render(<BlockEditor snapshotId="s" block={block} onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByLabelText("cell 0,0")).toBeTruthy();
  });

  it("renders the prose editor for a prose block", () => {
    const block: PackBlockOut = { id: "b", type: "prose", content: "x" };
    render(<BlockEditor snapshotId="s" block={block} onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByLabelText("Prose (Markdown)")).toBeTruthy();
  });
});
