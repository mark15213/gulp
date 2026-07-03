"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { capture } from "@gulp/api-client";
import { enqueuePending } from "@/lib/captureQueue";
import { Button } from "@/components/ui/Button";
import styles from "./CaptureSheet.module.css";

type Mode = "link" | "note";

export function CaptureSheet({ onClose }: { onClose: () => void }) {
  const [mode, setMode] = useState<Mode>("link");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const canSave = mode === "link" ? url.trim().length > 0 : text.trim().length > 0;

  async function onSave() {
    const tags: string[] = [];
    const body =
      mode === "link"
        ? { url, title: title || undefined, tags, captured_via: "paste" as const }
        : { text, title: title || undefined, tags, captured_via: "manual" as const };
    setError(null);
    try {
      await capture(body);
    } catch {
      // Only a genuinely-offline browser is safe to buffer optimistically. Any
      // other failure (server down, CORS, 4xx) must be surfaced — swallowing it
      // into the local queue is how captures silently vanished.
      if (typeof navigator !== "undefined" && !navigator.onLine) {
        enqueuePending({
          localId: crypto.randomUUID(),
          ...(mode === "link" ? { url } : { text }),
          title: title || undefined,
          tags,
          captured_via: mode === "link" ? "paste" : "manual",
        });
      } else {
        setError("Couldn't save — the server didn't respond. Nothing was saved; try again.");
        return;
      }
    }
    onClose();
    router.refresh();
  }

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.sheet} onClick={(e) => e.stopPropagation()}>
        <div className={styles.tabs}>
          <button
            className={mode === "link" ? styles.tabActive : styles.tab}
            onClick={() => setMode("link")}
          >
            Link
          </button>
          <button
            className={mode === "note" ? styles.tabActive : styles.tab}
            onClick={() => setMode("note")}
          >
            Note
          </button>
        </div>

        {mode === "link" ? (
          <input
            className={styles.input}
            placeholder="Paste a link…"
            autoFocus
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        ) : (
          <textarea
            className={styles.textarea}
            placeholder="Write a note…"
            autoFocus
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        )}

        <input
          className={styles.input}
          placeholder="Title (optional)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        {error && (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        )}

        <div className={styles.actions}>
          <span className={styles.target}>→ Inbox</span>
          <Button variant="primary" disabled={!canSave} onClick={onSave}>
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}
