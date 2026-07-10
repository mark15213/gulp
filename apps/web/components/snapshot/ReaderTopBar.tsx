"use client";

import React from "react";
import Link from "next/link";
import { IconConversation } from "@/components/ui/icons";
import { GenreSelect } from "./GenreSelect";
import styles from "./ReaderTopBar.module.css";

export function ReaderTopBar({
  title,
  genre,
  snapshotId,
  originUrl,
  navOpen,
  onToggleNav,
  chatEnabled,
  chatOpen,
  onToggleChat,
}: {
  title: string;
  genre: React.ComponentProps<typeof GenreSelect>["genre"];
  snapshotId: string;
  originUrl: string | null;
  navOpen: boolean;
  onToggleNav: () => void;
  chatEnabled: boolean;
  chatOpen: boolean;
  onToggleChat: () => void;
}) {
  return (
    <header className={styles.bar}>
      <button
        type="button"
        className={`${styles.icon} ${styles.navToggle}`}
        aria-label={navOpen ? "Hide sidebar" : "Show sidebar"}
        aria-pressed={navOpen}
        onClick={onToggleNav}
      >
        ⇤
      </button>
      <Link href="/inbox" className={styles.back}>
        ← Inbox
      </Link>
      <h1 className={`t-title-m ${styles.title}`}>{title}</h1>
      <GenreSelect snapshotId={snapshotId} genre={genre} />
      <span className={styles.spacer} />
      {originUrl && (
        <a
          className={styles.icon}
          href={originUrl}
          target="_blank"
          rel="noreferrer"
          aria-label="Open original"
          title="Open original"
        >
          ↗
        </a>
      )}
      {chatEnabled && (
        <button
          type="button"
          className={styles.icon}
          aria-label="Toggle chat"
          aria-pressed={chatOpen}
          onClick={onToggleChat}
        >
          <IconConversation />
        </button>
      )}
    </header>
  );
}
