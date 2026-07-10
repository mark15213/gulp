"use client";

import React from "react";
import Link from "next/link";
import type { Subscription } from "@gulp/api-client";
import { IconTrash } from "@/components/ui/icons";
import styles from "./SubscriptionList.module.css";

function RefreshGlyph() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path d="M20 11a8 8 0 1 0-2.3 5.7" />
      <path d="M20 5v6h-6" />
    </svg>
  );
}

function BellGlyph({ muted }: { muted: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path d="M18 8a6 6 0 0 0-9.4-5" />
      <path d="M6 8c0 7-3 7-3 9h13" />
      <path d="M10 21h4" />
      {muted ? <path d="M3 3l18 18" /> : <path d="M18 8c0 3.7.8 5.4 1.6 6.6" />}
    </svg>
  );
}

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
        className={`${styles.allRow} ${selectedId === null ? styles.selected : ""}`}
        aria-pressed={selectedId === null}
        onClick={() => onSelect(null)}
      >
        All feeds
      </button>
      <ul className={styles.list}>
        {subscriptions.map((sub) => (
          <li
            key={sub.id}
            className={`${styles.row} ${selectedId === sub.id ? styles.selected : ""} ${
              sub.health === "muted" ? styles.mutedRow : ""
            }`}
          >
            <span
              className={`${styles.dot} ${styles[sub.health]}`}
              title={
                sub.health === "error"
                  ? (sub.last_fetch_error ?? "fetch error")
                  : sub.health
              }
              aria-hidden="true"
            />
            <span className={styles.srOnly}>
              Feed status: {sub.health}
              {sub.health === "error" && sub.last_fetch_error
                ? `, ${sub.last_fetch_error}`
                : ""}
            </span>
            <button
              type="button"
              className={styles.title}
              aria-pressed={selectedId === sub.id}
              onClick={() => onSelect(sub.id)}
            >
              {sub.title}
            </button>
            {sub.health !== "active" && (
              <span
                className={`${styles.health} ${
                  sub.health === "error"
                    ? styles.healthError
                    : styles.healthMuted
                }`}
              >
                {sub.health === "error" ? "Error" : "Muted"}
              </span>
            )}
            {sub.unread_count > 0 && (
              <span className={`t-data ${styles.count}`}>
                {sub.unread_count}
              </span>
            )}
            <span className={styles.actions}>
              {onRefresh && (
                <button
                  type="button"
                  className={styles.action}
                  title="Fetch now"
                  aria-label={`Fetch ${sub.title} now`}
                  onClick={() => onRefresh(sub)}
                >
                  <RefreshGlyph />
                </button>
              )}
              <button
                type="button"
                className={styles.action}
                title={sub.muted ? "Unmute" : "Mute"}
                aria-label={`${sub.muted ? "Unmute" : "Mute"} ${sub.title}`}
                onClick={() => onToggleMute(sub)}
              >
                <BellGlyph muted={sub.muted} />
              </button>
              <button
                type="button"
                className={`${styles.action} ${styles.deleteAction}`}
                title="Unsubscribe"
                aria-label={`Unsubscribe from ${sub.title}`}
                onClick={() => onDelete(sub)}
              >
                <IconTrash />
              </button>
            </span>
          </li>
        ))}
      </ul>
      {subscriptions.length === 0 && (
        <p className={styles.empty}>
          No feeds yet — add one or explore Discover.
        </p>
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
