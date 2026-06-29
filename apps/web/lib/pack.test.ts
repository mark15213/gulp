import { describe, expect, it } from "vitest";
import { isProcessing, safeHost, statusLabel } from "./pack";

describe("isProcessing", () => {
  it("is true only for processing/queued", () => {
    expect(isProcessing("processing")).toBe(true);
    expect(isProcessing("queued")).toBe(true);
    expect(isProcessing("ready")).toBe(false);
    expect(isProcessing("needs_attention")).toBe(false);
  });
});

describe("statusLabel", () => {
  it("labels exported and the rest", () => {
    expect(statusLabel("exported")).toBe("Exported");
    expect(statusLabel("ready")).toBe("Ready");
    expect(statusLabel("unprocessed")).toBe("Not started");
  });
});

describe("safeHost", () => {
  it("returns host for a valid URL", () => {
    expect(safeHost("https://example.com/x")).toBe("example.com");
  });

  it("returns Note for a schemeless URL", () => {
    expect(safeHost("example.com")).toBe("Note");
  });

  it("returns Note for null", () => {
    expect(safeHost(null)).toBe("Note");
  });
});
