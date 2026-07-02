import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PackBlockOut } from "@gulp/api-client";
import { ListEditor } from "./ListEditor";
import { TableEditor } from "./TableEditor";

afterEach(cleanup);

describe("structural editors", () => {
  it("ListEditor splits lines into items, drops blank lines, keeps ordered flag", async () => {
    const block: PackBlockOut = { id: "b", type: "list", items: ["one", "two"], ordered: false };
    const onSave = vi.fn();
    render(<ListEditor block={block} onSave={onSave} onCancel={vi.fn()} />);
    const ta = screen.getByLabelText("List items (one per line)");
    await userEvent.clear(ta);
    await userEvent.type(ta, "a{enter}{enter}b");
    await userEvent.click(screen.getByLabelText("Ordered list"));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith({ type: "list", items: ["a", "b"], ordered: true });
  });

  it("TableEditor edits a cell and adds a row, then emits the grid", async () => {
    const block: PackBlockOut = {
      id: "b",
      type: "table",
      headers: ["H1", "H2"],
      rows: [["a", "b"]],
      caption: null,
    };
    const onSave = vi.fn();
    render(<TableEditor block={block} onSave={onSave} onCancel={vi.fn()} />);
    const cell = screen.getByLabelText("cell 0,0");
    await userEvent.clear(cell);
    await userEvent.type(cell, "X");
    await userEvent.click(screen.getByRole("button", { name: "Add row" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith({
      type: "table",
      headers: ["H1", "H2"],
      rows: [["X", "b"], ["", ""]],
      caption: null,
    });
  });
});
