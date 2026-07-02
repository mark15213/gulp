"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import type { Snapshot } from "@gulp/api-client";
import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import { RowBadges } from "./RowBadges";
import { safeHost } from "@/lib/pack";
import styles from "./LibraryList.module.css";

export function LibraryList({ items }: { items: Snapshot[] }) {
  const [tag, setTag] = useState<string | null>(null);
  const tags = useMemo(
    () => Array.from(new Set(items.flatMap((i) => i.tags))).sort(),
    [items],
  );
  const shown = tag ? items.filter((i) => i.tags.includes(tag)) : items;

  if (items.length === 0) {
    return <p className={styles.empty}>Nothing here yet — capture something and run it.</p>;
  }

  return (
    <div>
      {tags.length > 0 && (
        <div className={styles.chips}>
          <button
            type="button"
            className={`${styles.chip} ${tag === null ? styles.chipActive : ""}`}
            onClick={() => setTag(null)}
          >
            All
          </button>
          {tags.map((t) => (
            <button
              key={t}
              type="button"
              className={`${styles.chip} ${tag === t ? styles.chipActive : ""}`}
              onClick={() => setTag(t)}
            >
              {t}
            </button>
          ))}
        </div>
      )}
      <ul className={styles.list}>
        {shown.map((item) => (
          <li key={item.id} className={styles.row}>
            <ObjectGlyph type="snapshot" />
            <div className={styles.text}>
              <Link href={`/snapshots/${item.id}`} className={styles.title}>
                {item.title}
              </Link>
              <span className={`t-data ${styles.meta}`}>
                {safeHost(item.origin_url)}
                {item.tags.length > 0 && ` · ${item.tags.join(" · ")}`}
              </span>
            </div>
            <RowBadges mediaType={item.media_type} cardsStatus={item.cards_status} />
          </li>
        ))}
      </ul>
    </div>
  );
}
