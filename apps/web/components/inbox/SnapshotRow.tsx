"use client";

import React from "react";
import Link from "next/link";
import type { Snapshot } from "@gulp/api-client";
import { safeHost } from "@/lib/pack";
import { timeAgo } from "@/lib/time";
import type { StageKey } from "./stages";
import styles from "./InboxWorkspace.module.css";

function provenance(item: Snapshot): string {
  return item.source_feed?.title ?? safeHost(item.origin_url) ?? "Captured";
}

/** Stages 2–4. The title links to the reader at any status — that page shows
 *  Start / skeleton / banner / pack as appropriate, so "open it and watch the
 *  pack fill in" is one continuous path (spec §4.6). */
export function SnapshotRow({
  item,
  stage,
  done,
  selected,
  cursor,
  checked,
  onCheck,
  onSelect,
  onStart,
  onExport,
  onDelete,
}: {
  item: Snapshot;
  stage: StageKey;
  /** Reached `ready` while the user was on this surface — the belt's last frame. */
  done?: boolean;
  selected: boolean;
  cursor: boolean;
  checked?: boolean;
  onCheck?: (checked: boolean) => void;
  onSelect: () => void;
  onStart?: () => void;
  onExport?: () => void;
  onDelete?: () => void;
}) {
  const inFlight = stage === "flight" && !done;
  return (
    <li
      className={`${styles.row} ${inFlight ? styles.flight : ""} ${done ? styles.done : ""} ${
        selected ? styles.selected : ""
      } ${cursor ? styles.cursor : ""}`}
    >
      {onCheck ? (
        <input
          type="checkbox"
          className={styles.check}
          checked={!!checked}
          aria-label={`Select ${item.title}`}
          onChange={(e) => onCheck(e.target.checked)}
        />
      ) : (
        <span className={styles.pip} aria-hidden="true" />
      )}
      {/* Clicking the row peeks; clicking the title goes to the reader. */}
      <div className={styles.body} onClick={onSelect} role="presentation">
        <Link href={`/snapshots/${item.id}`} className={styles.title}>
          {item.title}
        </Link>
        <span className={`t-data ${styles.meta}`}>
          <span>{provenance(item)}</span>
          <span>· {timeAgo(item.created_at)}</span>
          {stage === "needs" && (
            <span
              className={`${styles.chip} ${
                item.status === "needs_attention" ? styles.chipAttention : ""
              }`}
            >
              {item.status === "needs_attention" ? "needs attention" : "awaiting upload"}
            </span>
          )}
          {stage === "flight" && (
            <span className={`${styles.chip} ${done ? styles.chipReady : ""}`}>
              {done ? "ready" : item.status}
            </span>
          )}
        </span>
      </div>
      <span className={styles.actions}>
        {done ? (
          <Link href={`/snapshots/${item.id}`} className={`${styles.action} ${styles.act}`}>
            Read →
          </Link>
        ) : (
          <>
            {onStart && (
              <button
                type="button"
                className={`${styles.action} ${styles.act}`}
                onClick={onStart}
              >
                {item.status === "needs_attention" ? "Retry" : "▶ Start"}
              </button>
            )}
            {onExport && (
              <button type="button" className={styles.action} onClick={onExport}>
                ⤓ Export
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                className={`${styles.action} ${styles.danger}`}
                onClick={onDelete}
              >
                Delete
              </button>
            )}
          </>
        )}
      </span>
    </li>
  );
}
