"use client";

import React, { useState } from "react";
import type { CardsImportBody } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import styles from "./Cards.module.css";

export function ImportDialog({
  onImport,
  onClose,
}: {
  onImport: (body: CardsImportBody) => Promise<void>;
  onClose: () => void;
}) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function readFile(file: File | undefined) {
    if (!file) return;
    setText(await file.text());
  }

  async function submit() {
    setError(null);
    let body: CardsImportBody;
    try {
      body = JSON.parse(text) as CardsImportBody;
    } catch {
      setError("Not valid JSON — paste the cards.json content.");
      return;
    }
    setBusy(true);
    try {
      await onImport(body);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.dialog}>
      <p className={styles.hint}>
        Paste a cards.json matching schema/cards.schema.json (also shipped in the export
        zip), or pick a file.
      </p>
      <input
        type="file"
        accept=".json,application/json"
        aria-label="cards.json file"
        onChange={(e) => void readFile(e.target.files?.[0])}
      />
      <textarea
        aria-label="Paste cards.json"
        className={styles.input}
        rows={8}
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={busy}
      />
      {error && (
        <div className={styles.err} role="alert">
          {error}
        </div>
      )}
      <div className={styles.rowActions}>
        <Button variant="primary" onClick={submit} disabled={busy || !text.trim()}>
          Import
        </Button>
        <Button onClick={onClose} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
