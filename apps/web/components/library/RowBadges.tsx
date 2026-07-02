import React from "react";
import type { Snapshot } from "@gulp/api-client";
import styles from "./RowBadges.module.css";

// Per-row source indicators for the Library shelf (spec 2026-07-02-library-
// width-and-source-badges): content form + cards state. Display-only; reuses
// the StateChip pill language — a text label is always present (never
// color-only).
const MEDIA_LABELS: Record<NonNullable<Snapshot["media_type"]>, string> = {
  article: "Article",
  pdf: "PDF",
  video: "Video",
  podcast: "Podcast",
  note: "Note",
  screenshot: "Screenshot",
  audio: "Audio",
  webpage: "Webpage",
};

const CARDS: Record<
  NonNullable<Snapshot["cards_status"]>,
  { label: string; variant: string }
> = {
  generating: { label: "Cards…", variant: "generating" },
  ready: { label: "✓ Cards", variant: "ready" },
  failed: { label: "⚠ Cards", variant: "failed" },
};

export function RowBadges({
  mediaType,
  cardsStatus,
}: {
  mediaType: Snapshot["media_type"];
  cardsStatus: Snapshot["cards_status"];
}) {
  const cards = cardsStatus ? CARDS[cardsStatus] : null;
  if (!mediaType && !cards) return null;
  return (
    <span className={styles.badges}>
      {mediaType && <span className={styles.media}>{MEDIA_LABELS[mediaType]}</span>}
      {cards && (
        <span className={`${styles.cards} ${styles[cards.variant]}`}>{cards.label}</span>
      )}
    </span>
  );
}
