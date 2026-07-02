import React from "react";
import { Button } from "@/components/ui/Button";
import { IconArrowRight } from "@/components/ui/icons";
import styles from "./StartGulpCard.module.css";

// The "what to do now" hero (docs/03 §7.9). Counts are live (accepted cards
// across the library); the practice loop itself ships with scheduling (S5),
// so the CTA stays disabled until then.
export function StartGulpCard({
  acceptedCards,
  cardSources,
}: {
  acceptedCards: number;
  cardSources: number;
}) {
  return (
    <section className={styles.hero}>
      <div className={styles.body}>
        <p className="t-label">Ready to practice</p>
        <p className={styles.count}>
          <span className={styles.num}>{acceptedCards}</span>
          <span className={styles.unit}>cards ready</span>
        </p>
        <p className={styles.meta}>
          {acceptedCards > 0 ? (
            <>
              across <span className="t-data">{cardSources}</span>{" "}
              {cardSources === 1 ? "source" : "sources"} in your library
            </>
          ) : (
            <>Accept cards on a ready snapshot to build your deck.</>
          )}
        </p>
      </div>

      <div className={styles.action}>
        <Button variant="primary" size="lg" disabled iconRight={<IconArrowRight />}>
          Start Gulp
        </Button>
        <p className={styles.actionHint}>Practice mode is coming soon</p>
      </div>
    </section>
  );
}
