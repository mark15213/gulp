import { describe, expect, it } from "vitest";
import { filterEntries, type SearchEntry } from "./search";

const entries: SearchEntry[] = [
  { id: "1", title: "The Bitter Lesson", tags: ["ai"], href: "/snapshots/1", kind: "snapshot" },
  { id: "2", title: "Spaced repetition", tags: ["memory"], href: "/snapshots/2", kind: "snapshot" },
  { id: "3", title: "Inbox", tags: [], href: "/inbox", kind: "page" },
];

describe("filterEntries", () => {
  it("returns the head of the list for an empty query", () => {
    expect(filterEntries(entries, "  ")).toEqual(entries);
  });

  it("matches titles case-insensitively", () => {
    expect(filterEntries(entries, "BITTER").map((e) => e.id)).toEqual(["1"]);
  });

  it("matches tags", () => {
    expect(filterEntries(entries, "memory").map((e) => e.id)).toEqual(["2"]);
  });

  it("caps results at the limit", () => {
    const many = Array.from({ length: 12 }, (_, i) => ({
      id: String(i),
      title: `note ${i}`,
      tags: [],
      href: `/snapshots/${i}`,
      kind: "snapshot" as const,
    }));
    expect(filterEntries(many, "note")).toHaveLength(8);
  });
});
