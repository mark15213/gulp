"use client";

import React, { useState } from "react";
import type { CardOut, CardPatchBody } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import { StateChip } from "@/components/ui/StateChip";
import styles from "./Cards.module.css";

const ORIGIN_LABEL: Record<CardOut["origin"], string> = {
  pack: "AI",
  imported: "Imported",
  user: "Manual",
  conversation: "Chat",
};

export function CardRow({
  card,
  onStatusChange,
  onDelete,
  onSave,
}: {
  card: CardOut;
  onStatusChange: (next: CardOut["status"]) => void;
  onDelete: () => void;
  onSave: (patch: CardPatchBody) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [prompt, setPrompt] = useState(card.prompt);
  const [answer, setAnswer] = useState(card.answer ?? "");
  const [explanation, setExplanation] = useState(card.explanation ?? "");
  const [options, setOptions] = useState((card.options ?? []).join("\n"));
  const [rowError, setRowError] = useState<string | null>(null);

  async function save() {
    setRowError(null);
    const patch: CardPatchBody = {
      prompt,
      answer: answer.trim() ? answer : null,
      explanation: explanation.trim() ? explanation : null,
    };
    if (card.card_type === "mcq") {
      patch.options = options
        .split("\n")
        .map((o) => o.trim())
        .filter(Boolean);
    }
    try {
      await onSave(patch);
      setEditing(false);
    } catch {
      setRowError("Couldn't save — check the fields (mcq answer must be one of the options).");
    }
  }

  return (
    <li className={styles.row}>
      <div className={styles.meta}>
        <span className={`t-label ${styles.type}`}>{card.card_type.replace(/_/g, " ")}</span>
        <span className={`t-label ${styles.origin}`}>{ORIGIN_LABEL[card.origin]}</span>
        {card.status !== "draft" && (
          <span className={`t-label ${styles[card.status]}`}>{card.status}</span>
        )}
        {card.daily && <StateChip state={card.daily} />}
      </div>
      {editing ? (
        <div className={styles.editor}>
          <textarea
            aria-label="Prompt"
            className={styles.input}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <textarea
            aria-label="Answer"
            className={styles.input}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
          />
          <textarea
            aria-label="Explanation"
            className={styles.input}
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
          />
          {card.card_type === "mcq" && (
            <textarea
              aria-label="Options (one per line)"
              className={styles.input}
              value={options}
              onChange={(e) => setOptions(e.target.value)}
            />
          )}
          {rowError && (
            <div className={styles.err} role="alert">
              {rowError}
            </div>
          )}
          <div className={styles.rowActions}>
            <Button variant="primary" onClick={save}>
              Save
            </Button>
            <Button onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <>
          <p className={styles.prompt}>{card.prompt}</p>
          {card.options && (
            <ul className={styles.options}>
              {card.options.map((o) => (
                <li key={o} className={o === card.answer ? styles.correct : undefined}>
                  {o}
                </li>
              ))}
            </ul>
          )}
          {!card.options && card.answer && <p className={styles.answer}>{card.answer}</p>}
          {card.explanation && <p className={styles.explanation}>{card.explanation}</p>}
          <div className={styles.rowActions}>
            {card.status !== "accepted" && (
              <Button onClick={() => onStatusChange("accepted")}>Accept</Button>
            )}
            {card.status !== "rejected" && (
              <Button onClick={() => onStatusChange("rejected")}>Reject</Button>
            )}
            <Button onClick={() => setEditing(true)}>Edit</Button>
            <Button onClick={onDelete}>Delete</Button>
          </div>
        </>
      )}
    </li>
  );
}
