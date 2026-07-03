import { describe, expect, it } from "vitest";
import { figureUrl } from "@gulp/api-client";

describe("figureUrl", () => {
  it("builds a bytes URL from ids", () => {
    expect(figureUrl("snap-1", "fig-2")).toMatch(/\/snapshots\/snap-1\/figures\/fig-2$/);
  });
});
