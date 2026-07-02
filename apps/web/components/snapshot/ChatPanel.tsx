"use client";

import React, { useEffect, useState } from "react";
import { getBlockMessages, postBlockMessage, type MessageOut } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import styles from "./ChatPanel.module.css";

export function ChatPanel({
  snapshotId,
  blockId,
  onClose,
}: {
  snapshotId: string;
  blockId: string;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setMessages([]);
    setError(null);
    getBlockMessages(snapshotId, blockId)
      .then((m) => {
        if (active) setMessages(m);
      })
      .catch(() => {
        if (active) setError("Couldn't load the conversation.");
      });
    return () => {
      active = false;
    };
  }, [snapshotId, blockId]);

  async function send() {
    const q = draft.trim();
    if (!q || sending) return;
    setError(null);
    setSending(true);
    setDraft("");
    const optimistic: MessageOut = { id: `tmp-${q}`, role: "user", content: q, created_at: "" };
    setMessages((m) => [...m, optimistic]);
    try {
      const answer = await postBlockMessage(snapshotId, blockId, { content: q });
      setMessages((m) => [...m, answer]);
    } catch {
      setMessages((m) => m.filter((x) => x.id !== optimistic.id));
      setDraft(q);
      setError("Couldn't send — try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <aside className={styles.panel} aria-label="Block chat">
      <div className={styles.header}>
        <span className="t-label">Discuss</span>
        <button type="button" className={styles.close} aria-label="Close chat" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className={styles.messages}>
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? styles.user : styles.assistant}>
            {m.content}
          </div>
        ))}
        {sending && <div className={styles.thinking}>Thinking…</div>}
      </div>
      {error && (
        <div className={styles.err} role="alert">
          {error}
        </div>
      )}
      <div className={styles.composer}>
        <textarea
          aria-label="Ask about this block"
          className={styles.input}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={sending}
        />
        <Button variant="primary" onClick={send} disabled={sending || !draft.trim()}>
          Send
        </Button>
      </div>
    </aside>
  );
}
