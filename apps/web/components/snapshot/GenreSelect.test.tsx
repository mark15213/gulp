import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import { GenreSelect } from "./GenreSelect";

vi.mock("@gulp/api-client", () => ({
  updateSnapshot: vi.fn(),
}));

afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

describe("GenreSelect", () => {
  it("shows the current genre and patches on change", async () => {
    (api.updateSnapshot as ReturnType<typeof vi.fn>).mockResolvedValue({});
    render(<GenreSelect snapshotId="snap-1" genre="article" />);
    const select = screen.getByLabelText("Genre") as HTMLSelectElement;
    expect(select.value).toBe("article");

    await userEvent.selectOptions(select, "paper");
    expect(api.updateSnapshot).toHaveBeenCalledWith("snap-1", { genre: "paper" });
    await waitFor(() =>
      expect(screen.getByText(/re-run processing/i)).toBeTruthy(),
    );
  });

  it("rolls back on a failed patch", async () => {
    (api.updateSnapshot as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("nope"));
    render(<GenreSelect snapshotId="snap-1" genre="article" />);
    const select = screen.getByLabelText("Genre") as HTMLSelectElement;
    await userEvent.selectOptions(select, "paper");
    await waitFor(() => expect(select.value).toBe("article"));
    expect(screen.getByText(/couldn't update/i)).toBeTruthy();
  });

  it("offers an unclassified placeholder when genre is null", () => {
    render(<GenreSelect snapshotId="snap-1" genre={null} />);
    const select = screen.getByLabelText("Genre") as HTMLSelectElement;
    expect(select.value).toBe("");
  });
});
