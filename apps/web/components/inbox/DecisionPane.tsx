"use client";

import React from "react";
import Link from "next/link";
import type { FeedEntry, Snapshot } from "@gulp/api-client";
import { sanitizeFeedHtml } from "@/lib/feeds";
import { safeHost, statusLabel } from "@/lib/pack";
import { timeAgo } from "@/lib/time";
import styles from "./InboxWorkspace.module.css";

/** Right pane — a decision preview, never a reader (spec §4.4). Its job is to
 *  answer keep-or-digest in about ten seconds; reading and chat live at
 *  /snapshots/{id}. */
export function DecisionPane({
  entry,
  snapshot,
  done,
  onForward,
  onSkip,
  onStart,
}: {
  entry: FeedEntry | null;
  snapshot: Snapshot | null;
  done?: boolean;
  onForward: (entry: FeedEntry) => void;
  onSkip: (entry: FeedEntry, skipped: boolean) => void;
  onStart: (snapshot: Snapshot) => void;
}) {
  if (entry) {
    return (
      <aside className={styles.preview} aria-label="Decision preview">
        <header className={styles.previewHead}>
          <h2>{entry.title}</h2>
          <p className={`t-data ${styles.previewMeta}`}>
            {entry.subscription_title}
            {entry.author ? ` · ${entry.author}` : ""}
            {entry.published_at ? ` · ${timeAgo(entry.published_at)}` : ""}
          </p>
          <div className={styles.previewActions}>
            {entry.skipped ? (
              <button
                type="button"
                className={styles.action}
                onClick={() => onSkip(entry, false)}
              >
                Undo skip
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className={`${styles.action} ${styles.act}`}
                  disabled={!entry.url}
                  onClick={() => onForward(entry)}
                >
                  Forward
                </button>
                <button
                  type="button"
                  className={styles.action}
                  onClick={() => onSkip(entry, true)}
                >
                  Skip
                </button>
              </>
            )}
            {entry.url && (
              <a
                className={styles.action}
                href={entry.url}
                target="_blank"
                rel="noreferrer"
              >
                Open original ↗
              </a>
            )}
          </div>
        </header>
        {entry.content_html ? (
          <div
            className={styles.previewBody}
            dangerouslySetInnerHTML={{ __html: sanitizeFeedHtml(entry.content_html) }}
          />
        ) : (
          <p className={styles.previewEmpty}>
            No content in the feed — open the original.
          </p>
        )}
      </aside>
    );
  }

  if (snapshot) {
    const startable =
      snapshot.status === "unprocessed" || snapshot.status === "needs_attention";
    return (
      <aside className={styles.preview} aria-label="Decision preview">
        <header className={styles.previewHead}>
          <h2>{snapshot.title}</h2>
          <p className={`t-data ${styles.previewMeta}`}>
            {done ? "ready" : statusLabel(snapshot.status)} ·{" "}
            {timeAgo(snapshot.created_at)}
          </p>
          <div className={styles.previewActions}>
            {done ? (
              <Link
                href={`/snapshots/${snapshot.id}`}
                className={`${styles.action} ${styles.act}`}
              >
                Read the pack →
              </Link>
            ) : (
              startable && (
                <button
                  type="button"
                  className={`${styles.action} ${styles.act}`}
                  onClick={() => onStart(snapshot)}
                >
                  {snapshot.status === "needs_attention" ? "Retry" : "▶ Start digesting"}
                </button>
              )
            )}
            <Link href={`/snapshots/${snapshot.id}`} className={styles.action}>
              Open
            </Link>
            {snapshot.origin_url && (
              <a
                className={styles.action}
                href={snapshot.origin_url}
                target="_blank"
                rel="noreferrer"
              >
                Original ↗
              </a>
            )}
          </div>
        </header>
        <div className={styles.previewBody}>
          {snapshot.status === "needs_attention" && (
            <p className={styles.error}>
              Couldn&apos;t fully read this. Retry, or open the original and capture
              the selection.
            </p>
          )}
          {snapshot.status === "exported" && (
            <p className={styles.note}>
              Exported — run the job, then upload the result from the reader.
            </p>
          )}
          <dl className={`t-data ${styles.kv}`}>
            <dt>Source</dt>
            <dd>{snapshot.source_feed?.title ?? "Captured"}</dd>
            <dt>Origin</dt>
            <dd>{safeHost(snapshot.origin_url) ?? "—"}</dd>
            <dt>Genre</dt>
            <dd>{snapshot.genre ?? "—"}</dd>
            <dt>Status</dt>
            <dd>{done ? "ready" : snapshot.status}</dd>
          </dl>
          {snapshot.note && <p className={styles.note}>{snapshot.note}</p>}
          <p>
            {done
              ? "Digested. Open it to read the pack and talk to it — it stays here until you leave, then lives in the Library."
              : "Reading happens in the pack. Opening the title works at any status — Start it there and watch it fill in."}
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside className={styles.preview} aria-label="Decision preview">
      <p className={styles.previewEmpty}>
        Pick a row. This pane answers keep-or-digest — reading happens in the pack.
      </p>
    </aside>
  );
}
