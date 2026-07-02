// ⌘K palette entries + matching. Client-side substring match over titles and
// tags — the corpus is one user's snapshots, so no server round-trip needed.

export interface SearchEntry {
  id: string;
  title: string;
  tags: string[];
  href: string;
  kind: "page" | "snapshot";
}

export function filterEntries(
  entries: SearchEntry[],
  query: string,
  limit = 8,
): SearchEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return entries.slice(0, limit);
  return entries
    .filter(
      (e) =>
        e.title.toLowerCase().includes(q) ||
        e.tags.some((t) => t.toLowerCase().includes(q)),
    )
    .slice(0, limit);
}
