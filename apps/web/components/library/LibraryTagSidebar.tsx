import React from "react";
import type { ActiveFilter, FacetEntry, LibraryFacets } from "@/lib/libraryFacets";
import styles from "./LibraryTagSidebar.module.css";

function Group({
  title,
  kind,
  entries,
  active,
  onSelect,
}: {
  title: string;
  kind: "source" | "tag";
  entries: FacetEntry[];
  active: ActiveFilter;
  onSelect: (f: ActiveFilter) => void;
}) {
  if (entries.length === 0) return null;
  return (
    <div className={styles.group}>
      <div className={styles.groupTitle}>{title}</div>
      {entries.map((e) => {
        const on = active?.kind === kind && active.value === e.value;
        return (
          <button
            key={e.value}
            type="button"
            className={`${styles.entry} ${on ? styles.entryActive : ""}`}
            onClick={() => onSelect(on ? null : { kind, value: e.value })}
          >
            <span className={styles.entryLabel}>{e.value}</span>
            <span className={styles.entryCount}>{e.count}</span>
          </button>
        );
      })}
    </div>
  );
}

export function LibraryTagSidebar({
  facets,
  active,
  onSelect,
}: {
  facets: LibraryFacets;
  active: ActiveFilter;
  onSelect: (f: ActiveFilter) => void;
}) {
  return (
    <aside className={styles.sidebar} aria-label="Filter library">
      <button
        type="button"
        className={`${styles.entry} ${active === null ? styles.entryActive : ""}`}
        onClick={() => onSelect(null)}
      >
        <span className={styles.entryLabel}>All</span>
      </button>
      <Group title="Sources" kind="source" entries={facets.sources} active={active} onSelect={onSelect} />
      <Group title="Mine" kind="tag" entries={facets.tags} active={active} onSelect={onSelect} />
      <div className={styles.group}>
        <div className={styles.groupTitle}>Topics</div>
        <div className={styles.comingSoon}>coming soon</div>
      </div>
    </aside>
  );
}
