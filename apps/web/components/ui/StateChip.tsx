import type { MasteryState } from "@/lib/mock";
import styles from "./StateChip.module.css";

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
  /** When set, a Due chip renders as a mono count badge ("3 due"). */
  count?: number;
}) {
  const label =
    state === "due" && count !== undefined
      ? `${count} due`
      : LABELS[state];

  return (
    <span className={`${styles.chip} ${styles[state]}`}>
      <span className={styles.dot} aria-hidden="true" />
      {state === "due" && count !== undefined ? (
        <span className={styles.count}>{label}</span>
      ) : (
        label
      )}
    </span>
  );
}
