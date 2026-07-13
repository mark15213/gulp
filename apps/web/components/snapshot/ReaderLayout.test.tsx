import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReaderLayout } from "./ReaderLayout";

vi.mock("@gulp/api-client", () => ({
  getPackMessages: vi.fn().mockResolvedValue([]),
  streamPackMessage: vi.fn(() =>
    (async function* () {
      yield { type: "done", message: {} };
    })(),
  ),
}));
vi.mock("./GenreSelect", () => ({ GenreSelect: () => <div>genre</div> }));

afterEach(cleanup);

function renderReader(
  packReady = true,
  originUrl: string | null = "https://x.com/a",
) {
  return render(
    <ReaderLayout
      sidebar={<nav>SIDENAV</nav>}
      snapshotId="s1"
      title="My Article"
      genre={null}
      originUrl={originUrl}
      packReady={packReady}
    >
      <div>BODY</div>
    </ReaderLayout>,
  );
}

describe("ReaderLayout", () => {
  it("toggles the nav", async () => {
    renderReader();
    expect(screen.getByText("SIDENAV")).toBeTruthy();
    const hide = screen.getByRole("button", { name: /Hide sidebar/ });
    expect(hide.getAttribute("aria-pressed")).toBe("true");
    await userEvent.click(hide);
    expect(screen.queryByText("SIDENAV")).toBeNull();
    expect(
      screen
        .getByRole("button", { name: /Show sidebar/ })
        .getAttribute("aria-pressed"),
    ).toBe("false");
  });

  it("toggles the chat panel when the pack is ready", async () => {
    renderReader(true);
    expect(
      screen.queryByRole("complementary", { name: "Article chat" }),
    ).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Toggle chat" }));
    expect(
      screen.getByRole("complementary", { name: "Article chat" }),
    ).toBeTruthy();
  });

  it("shows the origin link and hides the chat toggle when not ready", () => {
    renderReader(false);
    expect(screen.getByRole("link", { name: /Open original/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Toggle chat" })).toBeNull();
  });
});
