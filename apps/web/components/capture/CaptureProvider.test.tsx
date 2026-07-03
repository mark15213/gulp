import React from "react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { cleanup, render } from "@testing-library/react";
import * as queue from "@/lib/captureQueue";
import { CaptureProvider } from "./CaptureProvider";

vi.mock("@/lib/captureQueue", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/captureQueue")>();
  return { ...actual, flushQueue: vi.fn() };
});

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("CaptureProvider", () => {
  it("flushes the pending capture queue on mount", () => {
    (queue.flushQueue as Mock).mockResolvedValue(0);
    render(
      <CaptureProvider>
        <div>child</div>
      </CaptureProvider>,
    );
    expect(queue.flushQueue).toHaveBeenCalledTimes(1);
  });
});
