"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  deleteCard,
  generateCards,
  getCards,
  getSnapshot,
  importCards,
  updateCard,
  type CardOut,
  type CardPatchBody,
  type CardsImportBody,
} from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import { CardRow } from "./CardRow";
import { ImportDialog } from "./ImportDialog";
import styles from "./Cards.module.css";

type CardsStatus = "generating" | "ready" | "failed" | null;

export function CardsView({
  snapshotId,
  initialCardsStatus,
  pollMs = 2500,
}: {
  snapshotId: string;
  initialCardsStatus: CardsStatus;
  pollMs?: number;
}) {
  const [cards, setCards] = useState<CardOut[]>([]);
  const [status, setStatus] = useState<CardsStatus>(initialCardsStatus);
  const [error, setError] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const refetch = useCallback(async () => {
    try {
      setCards(await getCards(snapshotId));
    } catch {
      setError("Couldn't load cards.");
    }
  }, [snapshotId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  // While the worker job runs, poll the snapshot until cards_status settles.
  useEffect(() => {
    if (status !== "generating") return;
    const timer = setInterval(async () => {
      try {
        const snap = await getSnapshot(snapshotId);
        const next = (snap.cards_status ?? null) as CardsStatus;
        if (next === "generating") return;
        clearInterval(timer);
        setStatus(next);
        if (next === "ready") await refetch();
        if (next === "failed") setError("Card generation failed — try again.");
      } catch {
        // transient poll failure: keep polling
      }
    }, pollMs);
    return () => clearInterval(timer);
  }, [status, snapshotId, pollMs, refetch]);

  async function onGenerate() {
    setError(null);
    try {
      await generateCards(snapshotId);
      setStatus("generating");
    } catch {
      setError("Couldn't start card generation — is the pack ready?");
    }
  }

  async function onStatusChange(card: CardOut, next: CardOut["status"]) {
    const prev = cards;
    setCards((cs) => cs.map((c) => (c.id === card.id ? { ...c, status: next } : c)));
    try {
      await updateCard(snapshotId, card.id, { status: next });
    } catch {
      setCards(prev);
      setError("Couldn't update the card — try again.");
    }
  }

  async function onDelete(card: CardOut) {
    const prev = cards;
    setCards((cs) => cs.filter((c) => c.id !== card.id));
    try {
      await deleteCard(snapshotId, card.id);
    } catch {
      setCards(prev);
      setError("Couldn't delete the card — try again.");
    }
  }

  async function onSave(card: CardOut, patch: CardPatchBody): Promise<void> {
    const updated = await updateCard(snapshotId, card.id, patch);
    setCards((cs) => cs.map((c) => (c.id === card.id ? updated : c)));
  }

  async function onImport(body: CardsImportBody): Promise<void> {
    const created = await importCards(snapshotId, body);
    setCards((cs) => [...cs, ...created]);
    setImportOpen(false);
  }

  const generating = status === "generating";

  return (
    <div className={styles.view}>
      <div className={styles.header}>
        <span className="t-label">Cards</span>
        <div className={styles.actions}>
          <Button onClick={onGenerate} disabled={generating}>
            Generate cards
          </Button>
          <Button onClick={() => setImportOpen(true)}>Import cards</Button>
        </div>
      </div>
      {generating && <p className={styles.status}>Drafting cards…</p>}
      {error && (
        <div className={styles.err} role="alert">
          {error}
        </div>
      )}
      {importOpen && (
        <ImportDialog onImport={onImport} onClose={() => setImportOpen(false)} />
      )}
      {cards.length === 0 && !generating ? (
        <p className={styles.empty}>
          No cards yet — generate them from the report, or import a cards.json.
        </p>
      ) : (
        <ul className={styles.list}>
          {cards.map((c) => (
            <CardRow
              key={c.id}
              card={c}
              onStatusChange={(next) => onStatusChange(c, next)}
              onDelete={() => onDelete(c)}
              onSave={(patch) => onSave(c, patch)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
