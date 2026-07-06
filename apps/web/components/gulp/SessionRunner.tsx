"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  completeGulpSession,
  reviewCard,
  type GulpSession,
  type GulpSummary,
  type SessionCard,
} from "@gulp/api-client";
import { StateChip } from "@/components/ui/StateChip";
import { CardPrompt } from "./CardPrompt";
import { Reveal } from "./Reveal";
import { GradeBar } from "./GradeBar";
import styles from "./Gulp.module.css";

export type Phase = "prompt" | "revealed";
// Derived from reviewCard's own signature (not hand-rolled) so this can't
// drift from the generated schema.
type Grade = Parameters<typeof reviewCard>[1]["grade"];
type Suggested = "got_it" | "missed";

// The queue state machine driving a Gulp session (S4 §7, Task 15), wired to
// the real <CardPrompt> (flashcard flip / mcq / cloze), <Reveal>, and
// <GradeBar> (Task 16). Task 17 swaps the "session complete" placeholder for
// the real summary and adds the why/snooze affordances. The state shape
// (queue/index/phase) and the grade()/reveal() seams survive both.
export function SessionRunner({ initial }: { initial: GulpSession }) {
  const sessionId = initial.id;
  const [queue, setQueue] = useState<SessionCard[]>(initial.cards);
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>("prompt");
  const [suggested, setSuggested] = useState<Suggested | undefined>(undefined);
  const [summary, setSummary] = useState<GulpSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const finishing = useRef(false);

  const current = queue[0] ?? null;
  const total = index + queue.length;
  const progressPct = total > 0 ? Math.round((index / total) * 100) : 0;

  // The queue drains either because the initial deck was already empty
  // (nothing due) or because the last grade() below emptied it. Either way,
  // draining ends the session — guarded so it only fires once.
  useEffect(() => {
    if (queue.length > 0 || summary || finishing.current) return;
    finishing.current = true;
    completeGulpSession(sessionId)
      .then(setSummary)
      .catch(() => setError("Couldn't finish the session — try again."));
  }, [queue.length, summary, sessionId]);

  // CardPrompt calls into this. `suggested` carries the mcq's implied grade
  // (correct pick → got_it, wrong pick → missed) so GradeBar can nudge
  // toward it without deciding for the learner.
  function reveal(suggestedGrade?: Suggested) {
    setSuggested(suggestedGrade);
    setPhase("revealed");
  }

  // Task 16's GradeBar calls into this. Submits the grade; if the server
  // hands back a retest card (a missed card re-queued for another pass this
  // session, per the prototype), it's folded onto the end of the local
  // queue so it surfaces again before the session ends.
  async function grade(g: Grade, response?: string) {
    if (!current || phase !== "revealed" || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await reviewCard(sessionId, {
        card_id: current.id,
        grade: g,
        response,
      });
      setQueue((prev) => {
        const rest = prev.slice(1);
        return result.next_card ? [...rest, result.next_card] : rest;
      });
      setIndex((i) => i + 1);
      setSuggested(undefined);
      setPhase("prompt");
    } catch {
      setError("Couldn't submit that grade — try again.");
    } finally {
      setBusy(false);
    }
  }

  if (summary) {
    return (
      <div className={styles.page}>
        <div className={styles.summary}>
          <p className={styles.summaryTitle}>Session complete</p>
          <p className={styles.summarySub}>{summary.reviewed_count} reviewed</p>
          {/* Task 17: stats grid (mastered / fuzzy / streak) + next-up */}
          <Link href="/" className={styles.backLink}>
            Back to Today
          </Link>
        </div>
      </div>
    );
  }

  if (!current) {
    // Empty deck: the effect above is completing the session; nothing to
    // show in the meantime.
    return <div className={styles.page} aria-live="polite" />;
  }

  return (
    <div className={styles.page}>
      <div className={styles.topbar}>
        <Link href="/" className={styles.iconBtn} aria-label="Exit session">
          ←
        </Link>
        <div className={styles.track}>
          <i style={{ width: `${progressPct}%` }} />
        </div>
        <span className={styles.counter}>
          {index} / {total}
        </span>
      </div>

      <div className={styles.stage}>
        <div className={styles.cardwrap}>
          <div className={styles.srcline}>
            <StateChip state={current.daily} />
            <span className={styles.srcName}>
              {current.source_title ?? "Untitled source"}
            </span>
          </div>

          <p className={styles.typeTag}>
            {current.card_type}
            {current.reason === "retest" ? " · retest" : ""}
          </p>
          <p className={styles.prompt}>{current.prompt}</p>

          {phase === "prompt" && (
            <CardPrompt key={current.id} card={current} onReveal={reveal} />
          )}

          {phase === "revealed" && <Reveal card={current} />}
        </div>
      </div>

      {error && (
        <p role="alert" className={styles.explain}>
          {error}
        </p>
      )}

      {/* Task 17 adds the snooze row alongside this */}
      {phase === "revealed" && (
        <GradeBar suggested={suggested} onGrade={(g) => void grade(g)} />
      )}
    </div>
  );
}
