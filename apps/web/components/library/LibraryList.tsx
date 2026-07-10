"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Snapshot } from "@gulp/api-client";
import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import { DeleteSnapshotButton } from "@/components/snapshot/DeleteSnapshotButton";
import { RowBadges } from "./RowBadges";
import { RowTags } from "./RowTags";
import { LibraryTagSidebar } from "./LibraryTagSidebar";
import { computeFacets, filterItems, type ActiveFilter } from "@/lib/libraryFacets";
import { safeHost } from "@/lib/pack";
import styles from "./LibraryList.module.css";

export function LibraryList({ items }: { items: Snapshot[] }) {
  // Local copy so tag edits are optimistic; re-sync when the server re-fetches
  // (e.g. after a delete calls router.refresh()).
  const [rows, setRows] = useState<Snapshot[]>(items);
  useEffect(() => setRows(items), [items]);
  const [active, setActive] = useState<ActiveFilter>(null);

  const facets = useMemo(() => computeFacets(rows), [rows]);
  const shown = useMemo(() => filterItems(rows, active), [rows, active]);

  if (items.length === 0) {
    return <p className={styles.empty}>Nothing here yet — capture something and run it.</p>;
  }

  function setTags(id: string, tags: string[]) {
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, tags } : r)));
  }

  return (
    <div className={styles.layout}>
      <LibraryTagSidebar facets={facets} active={active} onSelect={setActive} />
      <div className={styles.listCol}>
        {shown.length === 0 ? (
          <p className={styles.empty}>Nothing under “{active?.value}”.</p>
        ) : (
          <ul className={styles.list}>
            {shown.map((item) => (
              <li key={item.id} className={styles.row}>
                <ObjectGlyph type="snapshot" />
                <div className={styles.text}>
                  <Link href={`/snapshots/${item.id}`} className={styles.title}>
                    {item.title}
                  </Link>
                  <span className={`t-data ${styles.meta}`}>{safeHost(item.origin_url)}</span>
                  <RowTags
                    snapshotId={item.id}
                    sourceFeed={item.source_feed}
                    tags={item.tags}
                    onTagsChange={(t) => setTags(item.id, t)}
                    onSourceClick={(title) => setActive({ kind: "source", value: title })}
                  />
                </div>
                <RowBadges mediaType={item.media_type} cardsStatus={item.cards_status} />
                <DeleteSnapshotButton id={item.id} confirm />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
