import React from "react";
import Link from "next/link";
import type { GulpSummary } from "@gulp/api-client";
import styles from "./Gulp.module.css";

// The real "session complete" screen (S4 §7, prototype's `#summary`): a stat
// grid (reviewed / newly mastered / still fuzzy / streak) plus a "what to
// gulp next" line that deep-links into the two other places a session can
// pick up from — today's due queue and the inbox.
export function SessionSummary({ summary }: { summary: GulpSummary }) {
  const { due_count, inbox_count } = summary.next_up;

  return (
    <div className={styles.summary}>
      <p className={styles.summaryTitle}>Session complete</p>
      <p className={styles.summarySub}>Nice work — here&apos;s how it went</p>

      <div className={styles.stats}>
        <div className={styles.stat}>
          <p className={styles.statValue}>{summary.reviewed_count}</p>
          <p className={styles.statLabel}>reviewed</p>
        </div>
        <div className={`${styles.stat} ${styles.statMastered}`}>
          <p className={styles.statValue}>{summary.newly_mastered}</p>
          <p className={styles.statLabel}>newly mastered</p>
        </div>
        <div className={styles.stat}>
          <p className={styles.statValue}>{summary.still_fuzzy}</p>
          <p className={styles.statLabel}>still fuzzy</p>
        </div>
        <div className={`${styles.stat} ${styles.statStreak}`}>
          <p className={styles.statValue}>{summary.streak_days}</p>
          <p className={styles.statLabel}>day streak</p>
        </div>
      </div>

      <div className={styles.nextUp}>
        <p className={styles.nextUpLabel}>What to gulp next</p>
        <p className={styles.nextUpText}>
          <Link href="/">
            {due_count} {due_count === 1 ? "card" : "cards"} due tomorrow
          </Link>
          {" · "}
          <Link href="/inbox">
            {inbox_count} {inbox_count === 1 ? "item" : "items"} waiting in your inbox
          </Link>
        </p>
      </div>

      <Link href="/" className={styles.backLink}>
        Back to Today
      </Link>
    </div>
  );
}
