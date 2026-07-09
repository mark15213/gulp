"use client";

import React from "react";
import Link from "next/link";
import type { FeedEntry } from "@gulp/api-client";
import { sanitizeFeedHtml } from "@/lib/feeds";
import { timeAgo } from "@/lib/time";
import styles from "./EntryReader.module.css";

// Right pane: feed-provided content + the one decisive action, Gulp —
// promote this entry into the snapshot pipeline (spec 2026-07-09 §5).
export function EntryReader({
  entry,
  onGulp,
  onToggleRead,
}: {
  entry: FeedEntry | null;
  onGulp: (entry: FeedEntry) => void;
  onToggleRead: (entry: FeedEntry) => void;
}) {
  if (!entry) {
    return (
      <section className={styles.pane} aria-label="Reader">
        <p className={styles.placeholder}>Select an entry to read it here.</p>
      </section>
    );
  }
  return (
    <section className={styles.pane} aria-label="Reader">
      <header className={styles.header}>
        <h1 className={styles.title}>
          {entry.url ? (
            <a href={entry.url} target="_blank" rel="noreferrer">
              {entry.title}
            </a>
          ) : (
            entry.title
          )}
        </h1>
        <p className={`t-data ${styles.meta}`}>
          {entry.subscription_title}
          {entry.author ? ` · ${entry.author}` : ""}
          {entry.published_at ? ` · ${timeAgo(entry.published_at)}` : ""}
        </p>
        <div className={styles.actions}>
          {entry.promoted_source_id ? (
            <Link href={`/snapshots/${entry.promoted_source_id}`} className={styles.inLibrary}>
              In library →
            </Link>
          ) : (
            <button
              type="button"
              className={styles.gulp}
              disabled={!entry.url}
              title={entry.url ? "Create a snapshot and digest it" : "Entry has no URL"}
              onClick={() => onGulp(entry)}
            >
              Gulp
            </button>
          )}
          <button type="button" className={styles.secondary} onClick={() => onToggleRead(entry)}>
            {entry.read ? "Mark unread" : "Mark read"}
          </button>
          {entry.url && (
            <a className={styles.secondary} href={entry.url} target="_blank" rel="noreferrer">
              Open original ↗
            </a>
          )}
        </div>
      </header>
      {entry.content_html ? (
        <article
          className={styles.body}
          dangerouslySetInnerHTML={{ __html: sanitizeFeedHtml(entry.content_html) }}
        />
      ) : (
        <p className={styles.placeholder}>No content in the feed — open the original.</p>
      )}
    </section>
  );
}
