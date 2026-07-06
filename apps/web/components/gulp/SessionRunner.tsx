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
import { Button } from "@/components/ui/Button";
import { StateChip } from "@/components/ui/StateChip";
import styles from "./Gulp.module.css";

export type Phase = "prompt" | "revealed";
// Derived from reviewCard's own signature (not hand-rolled) so this can't
// drift from the generated schema.
type Grade = Parameters<typeof reviewCard>[1]["grade"];

// The queue state machine driving a Gulp session (S4 §7, Task 15). This is
// the SHELL: Task 16 swaps the inline prompt/reveal markup below for a real
// <CardPrompt> (flashcard flip / mcq / cloze) and a polished <GradeBar>;
// Task 17 swaps the "session complete" placeholder for the real summary and
// adds the why/snooze affordances. The state shape (queue/index/phase) and
// the grade()/reveal() seams are meant to survive both.
export function SessionRunner({ initial }: { initial: GulpSession }) {
  const sessionId = initial.id;
  const [queue, setQueue] = useState<SessionCard[]>(initial.cards);
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>("prompt");
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

  function reveal() {
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

          {/* Task 16: replace with <CardPrompt> (flashcard flip / mcq / cloze) */}
          {phase === "prompt" && (
            <div className={styles.flip}>
              <Button variant="secondary" onClick={reveal}>
                Show answer
              </Button>
            </div>
          )}

          {phase === "revealed" && (
            <div className={styles.reveal}>
              <p className={styles.answer}>{current.answer}</p>
              {current.explanation && (
                <p className={styles.explain}>{current.explanation}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {error && (
        <p role="alert" className={styles.explain}>
          {error}
        </p>
      )}

      {/* Task 16: replace with <GradeBar>; Task 17 adds the snooze row */}
      {phase === "revealed" && (
        <div className={styles.gradebar}>
          <div className={styles.grades}>
            <button
              className={`${styles.gradeBtn} ${styles.gradeGot}`}
              disabled={busy}
              onClick={() => void grade("got_it")}
            >
              Got it
            </button>
            <button
              className={`${styles.gradeBtn} ${styles.gradeFuzzy}`}
              disabled={busy}
              onClick={() => void grade("fuzzy")}
            >
              Fuzzy
            </button>
            <button
              className={`${styles.gradeBtn} ${styles.gradeMiss}`}
              disabled={busy}
              onClick={() => void grade("missed")}
            >
              Missed
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
