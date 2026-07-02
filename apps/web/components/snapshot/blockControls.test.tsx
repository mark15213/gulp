import React from "react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BlockToolbar } from "./BlockToolbar";
import { AddBlockMenu } from "./AddBlockMenu";

afterEach(cleanup);

describe("block controls", () => {
  it("BlockToolbar fires handlers and disables move at edges", async () => {
    const onDelete = vi.fn();
    const onMoveUp = vi.fn();
    render(
      <BlockToolbar
        onEdit={vi.fn()}
        onDelete={onDelete}
        onMoveUp={onMoveUp}
        onMoveDown={vi.fn()}
        canMoveUp={false}
        canMoveDown={true}
      />,
    );
    expect((screen.getByRole("button", { name: "Move block up" }) as HTMLButtonElement).disabled).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Delete block" }));
    expect(onDelete).toHaveBeenCalled();
  });

  it("AddBlockMenu opens the picker and reports the chosen type", async () => {
    const onInsert = vi.fn();
    render(<AddBlockMenu onInsert={onInsert} />);
    await userEvent.click(screen.getByRole("button", { name: "Add block" }));
    await userEvent.click(screen.getByRole("button", { name: "Add table block" }));
    expect(onInsert).toHaveBeenCalledWith("table");
  });
});
