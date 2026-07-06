import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { GradeBar } from "./GradeBar";

afterEach(cleanup);

describe("GradeBar", () => {
  it("clicking Got it emits got_it", () => {
    const onGrade = vi.fn();
    render(<GradeBar onGrade={onGrade} />);
    fireEvent.click(screen.getByRole("button", { name: /got it/i }));
    expect(onGrade).toHaveBeenCalledWith("got_it");
  });

  it("pressing 3 emits missed", () => {
    const onGrade = vi.fn();
    render(<GradeBar onGrade={onGrade} />);
    fireEvent.keyDown(window, { key: "3" });
    expect(onGrade).toHaveBeenCalledWith("missed");
  });

  it("ignores number keys while an input is focused", () => {
    const onGrade = vi.fn();
    render(
      <div>
        <input data-testid="somewhere-else" />
        <GradeBar onGrade={onGrade} />
      </div>,
    );
    const input = screen.getByTestId("somewhere-else");
    input.focus();
    fireEvent.keyDown(input, { key: "1" });
    expect(onGrade).not.toHaveBeenCalled();
  });
});
