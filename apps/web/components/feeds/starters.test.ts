import { describe, expect, it } from "vitest";
import { STARTER_SOURCES } from "./starters";

describe("STARTER_SOURCES", () => {
  it("covers both address forms", () => {
    expect(STARTER_SOURCES.some((s) => s.feedUrl.startsWith("rsshub://"))).toBe(true);
    expect(STARTER_SOURCES.some((s) => s.feedUrl.startsWith("https://"))).toBe(true);
  });

  it("has unique addresses", () => {
    const urls = STARTER_SOURCES.map((s) => s.feedUrl);
    expect(new Set(urls).size).toBe(urls.length);
  });
});
