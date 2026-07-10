"use client";

import React from "react";
import Link from "next/link";
import type { FeedEntry } from "@gulp/api-client";
import { sanitizeFeedHtml } from "@/lib/feeds";
import { timeAgo } from "@/lib/time";
import styles from "./EntryReader.module.css";

// A forwarded entry's snapshot moves queued/processing (Inbox) -> ready (Library).
// Show that live so the marker never claims the library before processing is done.
const IN_LIBRARY = new Set(["ready", "exported"]);

function promotedMarker(status: FeedEntry["promoted_status"]): {
  label: string;
  className: string;
} {
  if (status && IN_LIBRARY.has(status)) {
    return { label: "In library →", className: styles.statusReady };
  }
  if (status === "needs_attention") {
    return { label: "Needs attention →", className: styles.statusAttention };
  }
  return { label: "Processing… →", className: styles.statusProcessing };
}

// Right pane: feed-provided content + the one decisive action — Forward (the
// internal "gulp"): send this entry into the capture pipeline. It lands in the
// Inbox and reaches the Library only once processing completes (spec 2026-07-09 §5).
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
  const marker = entry.promoted_source_id ? promotedMarker(entry.promoted_status) : null;
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
          {marker ? (
            <Link href={`/snapshots/${entry.promoted_source_id}`} className={marker.className}>
              {marker.label}
            </Link>
          ) : (
            <button
              type="button"
              className={styles.forward}
              disabled={!entry.url}
              title={entry.url ? "Forward into your Inbox and digest it" : "Entry has no URL"}
              onClick={() => onGulp(entry)}
            >
              Forward
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
