import { describe, expect, it } from "vitest";
import type { Snapshot } from "@gulp/api-client";
import { computeFacets, filterItems } from "./libraryFacets";

function item(o: Partial<Snapshot> = {}): Snapshot {
  return {
    id: "s1", kind: "snapshot", title: "T", note: null, status: "ready",
    media_type: "article", genre: null, origin_url: "https://a.com", content_body: null,
    captured_via: "feed", cards_status: null, tags: [], source_feed: null,
    created_at: "", updated_at: "", ...o,
  } as Snapshot;
}

describe("computeFacets", () => {
  it("groups sources and tags with counts, sorted by name", () => {
    const items = [
      item({ id: "1", source_feed: { id: "f1", title: "HF Paper Daily" }, tags: ["pretrain"] }),
      item({ id: "2", source_feed: { id: "f1", title: "HF Paper Daily" }, tags: [] }),
      item({ id: "3", source_feed: null, tags: ["pretrain", "rl"] }),
    ];
    const f = computeFacets(items);
    expect(f.sources).toEqual([{ value: "HF Paper Daily", count: 2 }]);
    expect(f.tags).toEqual([{ value: "pretrain", count: 2 }, { value: "rl", count: 1 }]);
  });
});

describe("filterItems", () => {
  const items = [
    item({ id: "1", source_feed: { id: "f1", title: "HF Paper Daily" }, tags: ["pretrain"] }),
    item({ id: "2", source_feed: null, tags: ["rl"] }),
  ];
  it("returns all when no filter is active", () => {
    expect(filterItems(items, null)).toHaveLength(2);
  });
  it("filters by source", () => {
    expect(filterItems(items, { kind: "source", value: "HF Paper Daily" }).map((i) => i.id)).toEqual(["1"]);
  });
  it("filters by tag", () => {
    expect(filterItems(items, { kind: "tag", value: "rl" }).map((i) => i.id)).toEqual(["2"]);
  });
});
