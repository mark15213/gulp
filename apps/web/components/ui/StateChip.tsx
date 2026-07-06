import React from "react";
import styles from "./StateChip.module.css";

// Mastery states (docs/03 §7.2) — real scheduling lands with S5.
export type MasteryState = "new" | "learning" | "known" | "due" | "at-risk";

// Mastery-state chip — the product's most-repeated component (docs/03 §7.2).
// Tinted pill + on-tint label + dot; label always present, never color-only.
const LABELS: Record<MasteryState, string> = {
  new: "New",
  learning: "Learning",
  known: "Known",
  due: "Due",
  "at-risk": "At risk",
};

export function StateChip({
  state,
  count,
}: {
  state: MasteryState;
  /** When set, renders as a mono count badge (e.g. "3 due", "84 known"). */
  count?: number;
}) {
  const label =
    count !== undefined ? `${count} ${LABELS[state].toLowerCase()}` : LABELS[state];

  return (
    <span className={`${styles.chip} ${styles[state]}`}>
      <span className={styles.dot} aria-hidden="true" />
      {count !== undefined ? <span className={styles.count}>{label}</span> : label}
    </span>
  );
}
