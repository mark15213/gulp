import { describe, expect, it } from "vitest";

import { exportOutcome } from "./export";

describe("exportOutcome", () => {
  it("is pending while the worker is still building", () => {
    expect(exportOutcome("unprocessed")).toEqual({ state: "pending" });
  });

  it("is ready (auto-download) once the job is exported", () => {
    expect(exportOutcome("exported")).toEqual({ state: "ready" });
  });

  it("is failed with a message when the build errored to needs_attention", () => {
    const outcome = exportOutcome("needs_attention");
    expect(outcome.state).toBe("failed");
    if (outcome.state === "failed") {
      expect(outcome.message).toMatch(/export failed/i);
    }
  });
});
