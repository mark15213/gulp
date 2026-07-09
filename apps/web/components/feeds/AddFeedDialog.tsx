"use client";

import React, { useState } from "react";
import styles from "./AddFeedDialog.module.css";

// Accepts all three canonical address forms (spec 2026-07-09 §3):
// rsshub://ns/path · /ns/path · https://… — the API normalizes.
export function AddFeedDialog({
  open,
  onClose,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (feedUrl: string, title: string | null) => Promise<void>;
}) {
  const [feedUrl, setFeedUrl] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(feedUrl.trim(), title.trim() || null);
      setFeedUrl("");
      setTitle("");
      onClose();
    } catch {
      setError("Could not add — check the address (rsshub://…, /route/path, or https://…).");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.backdrop} role="dialog" aria-label="Add feed">
      <form className={styles.dialog} onSubmit={submit}>
        <h2 className={styles.heading}>Add feed</h2>
        <input
          className={styles.input}
          placeholder="rsshub://ns/path, /ns/path, or https://…"
          value={feedUrl}
          onChange={(e) => setFeedUrl(e.target.value)}
          autoFocus
          required
        />
        <input
          className={styles.input}
          placeholder="Title (optional — taken from the feed)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        {error && <p className={styles.error}>{error}</p>}
        <div className={styles.buttons}>
          <button type="button" className={styles.cancel} onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className={styles.confirm} disabled={busy || !feedUrl.trim()}>
            {busy ? "Adding…" : "Subscribe"}
          </button>
        </div>
      </form>
    </div>
  );
}
