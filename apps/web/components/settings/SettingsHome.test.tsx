import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SettingsHome } from "./SettingsHome";

afterEach(cleanup);

describe("SettingsHome", () => {
  it("links the AI providers card to its page", () => {
    render(<SettingsHome />);
    const card = screen.getByRole("link", { name: /AI providers/ });
    expect(card.getAttribute("href")).toBe("/settings/ai");
  });

  it("greys out unimplemented sections as non-links", () => {
    render(<SettingsHome />);
    for (const label of ["Account", "Preferences", "Notifications"]) {
      const title = screen.getByText(label);
      const card = title.closest("[aria-disabled]");
      expect(card, `${label} card should be aria-disabled`).toBeTruthy();
      expect(card?.closest("a")).toBeNull();
    }
    expect(screen.getAllByText("Coming soon").length).toBe(3);
  });
});
