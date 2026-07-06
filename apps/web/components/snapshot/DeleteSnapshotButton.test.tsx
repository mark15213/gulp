import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import { DeleteSnapshotButton } from "./DeleteSnapshotButton";

const refresh = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, deleteSnapshot: vi.fn() };
});

const deleteMock = () => api.deleteSnapshot as ReturnType<typeof vi.fn>;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DeleteSnapshotButton", () => {
  it("deletes immediately (no confirm) and refreshes", async () => {
    deleteMock().mockResolvedValue(undefined);
    render(<DeleteSnapshotButton id="s1" />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(deleteMock()).toHaveBeenCalledWith("s1");
    await waitFor(() => expect(refresh).toHaveBeenCalled());
  });

  it("requires a second click (arm → confirm) when confirm is set", async () => {
    deleteMock().mockResolvedValue(undefined);
    render(<DeleteSnapshotButton id="s1" confirm />);

    // First click only arms — no API call yet, and the button relabels.
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(deleteMock()).not.toHaveBeenCalled();

    // Second click on the now-armed trash fires the delete.
    await userEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(deleteMock()).toHaveBeenCalledWith("s1");
    await waitFor(() => expect(refresh).toHaveBeenCalled());
  });

  it("cancel backs out of the armed state without deleting", async () => {
    render(<DeleteSnapshotButton id="s1" confirm />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(deleteMock()).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Delete" })).toBeTruthy();
  });

  it("shows a retryable error and does not refresh when delete fails", async () => {
    deleteMock().mockRejectedValue(new Error("boom"));
    render(<DeleteSnapshotButton id="s1" />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(refresh).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Delete" })).toBeTruthy(); // re-enabled
  });
});
