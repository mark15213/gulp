import React from "react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import * as queue from "@/lib/captureQueue";
import { CaptureSheet } from "./CaptureSheet";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, capture: vi.fn() };
});

vi.mock("@/lib/captureQueue", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/captureQueue")>();
  return { ...actual, enqueuePending: vi.fn() };
});

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

function setOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", { configurable: true, value });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  setOnline(true);
});

describe("CaptureSheet", () => {
  it("surfaces an error and keeps the sheet open when online and the request fails", async () => {
    setOnline(true);
    (api.capture as Mock).mockRejectedValue(new Error("unreachable"));
    const onClose = vi.fn();

    render(<CaptureSheet onClose={onClose} />);
    await userEvent.type(
      screen.getByPlaceholderText("Paste a link…"),
      "https://arxiv.org/pdf/2606.24775",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(queue.enqueuePending).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("buffers to the offline queue when the browser is offline", async () => {
    setOnline(false);
    (api.capture as Mock).mockRejectedValue(new Error("offline"));
    const onClose = vi.fn();

    render(<CaptureSheet onClose={onClose} />);
    await userEvent.type(screen.getByPlaceholderText("Paste a link…"), "https://a.com");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(queue.enqueuePending).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
