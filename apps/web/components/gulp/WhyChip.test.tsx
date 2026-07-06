import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { WhyChip } from "./WhyChip";

afterEach(cleanup);

describe("WhyChip", () => {
  it("starts collapsed, then toggles the reason's explanation on click", () => {
    render(<WhyChip reason="due" />);
    expect(screen.queryByText(/came due for review/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /why am i seeing this/i }));
    expect(screen.getByText(/came due for review/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /why am i seeing this/i }));
    expect(screen.queryByText(/came due for review/i)).toBeNull();
  });

  it.each([
    ["new", /new card/i],
    ["due", /came due for review/i],
    ["retest", /another pass/i],
    ["at_risk", /at risk of forgetting/i],
  ] as const)("maps reason %s to its explanation copy", (reason, expected) => {
    render(<WhyChip reason={reason} />);
    fireEvent.click(screen.getByRole("button", { name: /why am i seeing this/i }));
    expect(screen.getByText(expected)).toBeTruthy();
  });
});
