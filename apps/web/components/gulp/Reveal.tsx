import React from "react";
import type { SessionCard } from "@gulp/api-client";
import styles from "./Gulp.module.css";

// The answer + explanation, revealed after the learner commits to a prompt
// (S4 §7, prototype's `.reveal`). `explanation` is plain text — no markup.
export function Reveal({ card }: { card: SessionCard }) {
  return (
    <div className={styles.reveal}>
      <p className={styles.answer}>{card.answer}</p>
      {card.explanation && <p className={styles.explain}>{card.explanation}</p>}
    </div>
  );
}
