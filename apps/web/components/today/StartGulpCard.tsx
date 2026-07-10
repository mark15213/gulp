import React from "react";
import Link from "next/link";
import { IconArrowRight } from "@/components/ui/icons";
import styles from "./StartGulpCard.module.css";

// The "what to do now" hero (docs/03 §7.9). Counts are live (accepted cards
// across the library, plus today's due/new queue); the CTA hands off to the
// real practice loop at /gulp (S4 §7) — "Resume" when a session is already
// in progress, else "Start".
export function StartGulpCard({
  acceptedCards,
  cardSources,
  dueCount,
  newCount,
  hasResumable,
}: {
  acceptedCards: number;
  cardSources: number;
  dueCount: number;
  newCount: number;
  hasResumable: boolean;
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
        <Link href="/gulp" className={styles.cta}>
          {hasResumable ? "Resume Gulp" : "Start Gulp"}
          <IconArrowRight />
        </Link>
        <p className={styles.actionHint}>
          <span className="t-data">{dueCount}</span> due ·{" "}
          <span className="t-data">{newCount}</span> new
        </p>
      </div>
    </section>
  );
}
