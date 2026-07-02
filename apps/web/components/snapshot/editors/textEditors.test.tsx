import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PackBlockOut } from "@gulp/api-client";
import { ProseEditor } from "./ProseEditor";
import { FigureEditor } from "./FigureEditor";

afterEach(cleanup);

describe("text editors", () => {
  it("ProseEditor seeds from the block and emits edited content on Save", async () => {
    const block: PackBlockOut = { id: "b", type: "prose", content: "old" };
    const onSave = vi.fn();
    render(<ProseEditor block={block} onSave={onSave} onCancel={vi.fn()} />);
    const ta = screen.getByLabelText("Prose (Markdown)") as HTMLTextAreaElement;
    expect(ta.value).toBe("old");
    await userEvent.clear(ta);
    await userEvent.type(ta, "new text");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith({ type: "prose", content: "new text" });
  });

  it("FigureEditor emits label + explanation", async () => {
    const block: PackBlockOut = { id: "b", type: "figure", label: "L", explanation: "E" };
    const onSave = vi.fn();
    render(<FigureEditor block={block} onSave={onSave} onCancel={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith({ type: "figure", label: "L", explanation: "E" });
  });

  it("Cancel calls onCancel", async () => {
    const onCancel = vi.fn();
    render(
      <ProseEditor block={{ id: "b", type: "prose", content: "x" }} onSave={vi.fn()} onCancel={onCancel} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
  });
});
