"use client";

import React from "react";
import type { FeedEntry } from "@gulp/api-client";
import { timeAgo } from "@/lib/time";
import { triageOf } from "./stages";
import styles from "./InboxWorkspace.module.css";

/** Stage 1. The decision lives on the row — scan-and-keep must never require
 *  the preview pane (spec §4.3). An entry isn't yours yet, so its title opens
 *  the decision preview rather than a reader. */
export function EntryRow({
  entry,
  selected,
  cursor,
  onSelect,
  onForward,
  onSkip,
}: {
  entry: FeedEntry;
  selected: boolean;
  cursor: boolean;
  onSelect: () => void;
  onForward: () => void;
  onSkip: (skipped: boolean) => void;
}) {
  const triage = triageOf(entry);
  const state = triage === "skipped" ? styles.skipped : entry.read ? styles.seen : "";
  return (
    <li
      className={`${styles.row} ${state} ${selected ? styles.selected : ""} ${
        cursor ? styles.cursor : ""
      }`}
    >
      <span className={styles.pip} aria-hidden="true" />
      <div className={styles.body}>
        <button type="button" className={styles.title} onClick={onSelect}>
          {entry.title}
        </button>
        <span className={`t-data ${styles.meta}`}>
          <span>{entry.subscription_title}</span>
          {entry.published_at && <span>· {timeAgo(entry.published_at)}</span>}
        </span>
      </div>
      <span className={styles.actions}>
        {triage === "skipped" ? (
          <button type="button" className={styles.action} onClick={() => onSkip(false)}>
            Undo
          </button>
        ) : (
          <>
            <button
              type="button"
              className={`${styles.action} ${styles.act}`}
              disabled={!entry.url}
              title={entry.url ? "Take it in — you'll decide about digesting later" : "Entry has no URL"}
              onClick={onForward}
            >
              Forward
            </button>
            <button type="button" className={styles.action} onClick={() => onSkip(true)}>
              Skip
            </button>
          </>
        )}
      </span>
    </li>
  );
}
