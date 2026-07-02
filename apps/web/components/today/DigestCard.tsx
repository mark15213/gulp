import React from "react";
import Link from "next/link";
import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import { timeAgo } from "@/lib/time";
import type { TodayOut } from "@gulp/api-client";
import styles from "./DigestCard.module.css";

type TodayDigestItem = TodayOut["digest"][number];

// Object card (docs/03 §7.1): type glyph · title · optional note · mono meta.
// The mastery chip and "why it connects" line return when scheduling lands (S5).
export function DigestCard({ item }: { item: TodayDigestItem }) {
  const { snapshot } = item;
  const source = snapshot.origin_url ? new URL(snapshot.origin_url).host : "Note";
  return (
    <Link href={`/snapshots/${snapshot.id}`} className={styles.card}>
      <div className={styles.top}>
        <ObjectGlyph type="snapshot" />
      </div>

      <h3 className={`t-title-s ${styles.title}`}>{snapshot.title}</h3>
      {snapshot.note && (
        <p className={`t-body-s ${styles.summary}`}>{snapshot.note}</p>
      )}

      <div className={styles.meta}>
        <span className="t-data">{source}</span>
        <span className={styles.dot}>·</span>
        <span className="t-data">{timeAgo(snapshot.created_at)}</span>
        <span className={styles.cards}>
          <span className="t-data">+{item.accepted_cards}</span> cards
        </span>
      </div>
    </Link>
  );
}
