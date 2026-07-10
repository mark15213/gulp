"use client";

import React from "react";
import type { FeedEntry } from "@gulp/api-client";
import { timeAgo } from "@/lib/time";
import styles from "./EntryList.module.css";

// Middle pane: entries of the selected subscription (or all), newest first.
export function EntryList({
  entries,
  title,
  selectedId,
  onSelect,
  unreadOnly,
  onToggleUnreadOnly,
  onMarkAllRead,
}: {
  entries: FeedEntry[];
  title?: string;
  selectedId: string | null;
  onSelect: (id: string) => void;
  unreadOnly: boolean;
  onToggleUnreadOnly: () => void;
  onMarkAllRead?: () => void;
}) {
  return (
    <section className={styles.pane} aria-label="Entries">
      <header className={styles.header}>
        <h2 className={styles.heading}>{title ?? "All entries"}</h2>
        <span className={styles.controls}>
          {onMarkAllRead && (
            <button
              type="button"
              className={styles.control}
              onClick={onMarkAllRead}
            >
              Mark all read
            </button>
          )}
          <button
            type="button"
            className={`${styles.control} ${unreadOnly ? styles.controlActive : ""}`}
            aria-pressed={unreadOnly}
            onClick={onToggleUnreadOnly}
          >
            Unread
          </button>
        </span>
      </header>
      <ul className={styles.list}>
        {entries.map((entry) => (
          <li key={entry.id}>
            <button
              type="button"
              className={`${styles.row} ${selectedId === entry.id ? styles.active : ""} ${
                entry.read ? styles.read : ""
              }`}
              aria-pressed={selectedId === entry.id}
              onClick={() => onSelect(entry.id)}
            >
              <span className={styles.titleLine}>
                {!entry.read && (
                  <span className={styles.unreadDot} aria-label="unread" />
                )}
                <span className={styles.title}>{entry.title}</span>
                {entry.promoted_source_id && (
                  <span className={styles.forwarded} aria-label="forwarded">
                    ✓
                  </span>
                )}
              </span>
              <span className={`t-data ${styles.meta}`}>
                {entry.subscription_title}
                {entry.published_at ? ` · ${timeAgo(entry.published_at)}` : ""}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {entries.length === 0 && (
        <p className={styles.empty}>
          {unreadOnly
            ? "Nothing unread."
            : "No entries yet — feeds fill in after a fetch."}
        </p>
      )}
    </section>
  );
}
