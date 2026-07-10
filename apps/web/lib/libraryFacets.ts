import type { Snapshot } from "@gulp/api-client";

export type FacetEntry = { value: string; count: number };
export type LibraryFacets = { sources: FacetEntry[]; tags: FacetEntry[] };
export type ActiveFilter = { kind: "source" | "tag"; value: string } | null;

function toEntries(counts: Map<string, number>): FacetEntry[] {
  return Array.from(counts, ([value, count]) => ({ value, count })).sort((a, b) =>
    a.value.localeCompare(b.value),
  );
}

export function computeFacets(items: Snapshot[]): LibraryFacets {
  const sources = new Map<string, number>();
  const tags = new Map<string, number>();
  for (const it of items) {
    if (it.source_feed) {
      sources.set(it.source_feed.title, (sources.get(it.source_feed.title) ?? 0) + 1);
    }
    for (const t of it.tags) {
      tags.set(t, (tags.get(t) ?? 0) + 1);
    }
  }
  return { sources: toEntries(sources), tags: toEntries(tags) };
}

export function filterItems(items: Snapshot[], active: ActiveFilter): Snapshot[] {
  if (!active) return items;
  if (active.kind === "source") {
    return items.filter((i) => i.source_feed?.title === active.value);
  }
  return items.filter((i) => i.tags.includes(active.value));
}
