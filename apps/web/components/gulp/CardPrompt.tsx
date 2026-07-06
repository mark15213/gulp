"use client";

import React, { useEffect, useState } from "react";
import type { SessionCard } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import styles from "./Gulp.module.css";

type Suggested = "got_it" | "missed";

// The per-card-type interaction slot (S4 §7): flashcard flip, mcq options,
// cloze fill. Mount a fresh instance per card (parent keys on `card.id`) so
// each type's local state (picked option / typed value) doesn't leak across
// cards.
export function CardPrompt({
  card,
  onReveal,
}: {
  card: SessionCard;
  onReveal: (suggested?: Suggested) => void;
}) {
  if (card.card_type === "mcq") {
    return <McqPrompt card={card} onReveal={onReveal} />;
  }
  if (card.card_type === "cloze") {
    return <ClozePrompt onReveal={onReveal} />;
  }
  return <FlashcardPrompt onReveal={onReveal} />;
}

function FlashcardPrompt({ onReveal }: { onReveal: () => void }) {
  // Space reveals — mirrors the prototype's flashcard flip. Scoped to this
  // component's lifetime, so it's only live while the card is unrevealed.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target && target.tagName === "INPUT") return;
      if (e.code === "Space") {
        e.preventDefault();
        onReveal();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onReveal]);

  return (
    <div className={styles.flip}>
      <Button variant="secondary" onClick={() => onReveal()}>
        Show answer <kbd className={styles.kbd}>space</kbd>
      </Button>
    </div>
  );
}

function McqPrompt({
  card,
  onReveal,
}: {
  card: SessionCard;
  onReveal: (suggested?: Suggested) => void;
}) {
  const [picked, setPicked] = useState<number | null>(null);
  const options = card.options ?? [];

  function pick(index: number, option: string) {
    if (picked !== null) return;
    setPicked(index);
    onReveal(option === card.answer ? "got_it" : "missed");
  }

  return (
    <div className={styles.opts}>
      {options.map((option, index) => {
        const isAnswer = picked !== null && option === card.answer;
        const isWrongPick = picked === index && !isAnswer;
        const cls = [
          styles.opt,
          isAnswer ? styles.optCorrect : "",
          isWrongPick ? styles.optWrong : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <button
            key={index}
            type="button"
            className={cls}
            disabled={picked !== null}
            onClick={() => pick(index, option)}
          >
            <span className={styles.optKey}>{String.fromCharCode(65 + index)}</span>
            <span>{option}</span>
            {isAnswer && <span className={styles.optMark}>✓ answer</span>}
            {isWrongPick && <span className={styles.optMark}>your pick</span>}
          </button>
        );
      })}
    </div>
  );
}

function ClozePrompt({ onReveal }: { onReveal: () => void }) {
  const [value, setValue] = useState("");

  function submit() {
    onReveal();
  }

  return (
    <div className={styles.clozebox}>
      <input
        className={styles.clozeInput}
        type="text"
        placeholder="type the missing word…"
        autoComplete="off"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            submit();
          }
        }}
      />
      <Button variant="primary" onClick={submit}>
        Check
      </Button>
    </div>
  );
}
