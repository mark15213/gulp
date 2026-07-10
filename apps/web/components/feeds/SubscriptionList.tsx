"use client";

import React from "react";
import Link from "next/link";
import type { Subscription } from "@gulp/api-client";
import styles from "./SubscriptionList.module.css";

// Left pane (docs/03 §7.11): per-subscription health, mono unread count,
// mute toggle. Health is derived server-side: active / muted / error.
export function SubscriptionList({
  subscriptions,
  selectedId,
  onSelect,
  onToggleMute,
  onDelete,
  onRefresh,
  onAdd,
}: {
  subscriptions: Subscription[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onToggleMute: (sub: Subscription) => void;
  onDelete: (sub: Subscription) => void;
  onRefresh?: (sub: Subscription) => void;
  onAdd: () => void;
}) {
  return (
    <aside className={styles.pane} aria-label="Subscriptions">
      <button
        type="button"
        className={`${styles.allRow} ${selectedId === null ? styles.active : ""}`}
        onClick={() => onSelect(null)}
      >
        All feeds
      </button>
      <ul className={styles.list}>
        {subscriptions.map((sub) => (
          <li
            key={sub.id}
            className={`${styles.row} ${selectedId === sub.id ? styles.active : ""} ${
              sub.health === "muted" ? styles.mutedRow : ""
            }`}
          >
            <span
              className={`${styles.dot} ${styles[sub.health]}`}
              title={sub.health === "error" ? (sub.last_fetch_error ?? "fetch error") : sub.health}
            />
            <button type="button" className={styles.title} onClick={() => onSelect(sub.id)}>
              {sub.title}
            </button>
            {sub.unread_count > 0 && (
              <span className={`t-data ${styles.count}`}>{sub.unread_count}</span>
            )}
            <span className={styles.actions}>
              {onRefresh && (
                <button
                  type="button"
                  className={styles.action}
                  title="Fetch now"
                  onClick={() => onRefresh(sub)}
                >
                  ↻
                </button>
              )}
              <button
                type="button"
                className={styles.action}
                title={sub.muted ? "Unmute" : "Mute"}
                onClick={() => onToggleMute(sub)}
              >
                {sub.muted ? "🔕" : "🔔"}
              </button>
              <button
                type="button"
                className={styles.action}
                title="Unsubscribe"
                onClick={() => onDelete(sub)}
              >
                ✕
              </button>
            </span>
          </li>
        ))}
      </ul>
      {subscriptions.length === 0 && (
        <p className={styles.empty}>No feeds yet — add one or explore Discover.</p>
      )}
      <footer className={styles.footer}>
        <button type="button" className={styles.add} onClick={onAdd}>
          + Add feed
        </button>
        <Link href="/feeds/discover" className={styles.discover}>
          Discover →
        </Link>
      </footer>
    </aside>
  );
}
