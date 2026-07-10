"use client";

import React, { useEffect, useRef, useState } from "react";
import { getPackMessages, postPackMessage, type MessageOut } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import type { ChatAttachment } from "./ReaderChatContext";
import styles from "./ChatPanel.module.css";

export function ChatPanel({
  snapshotId,
  attachments,
  onRemoveAttachment,
  onClose,
}: {
  snapshotId: string;
  attachments: ChatAttachment[];
  onRemoveAttachment: (id: string) => void;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tmpIdRef = useRef(0);

  useEffect(() => {
    let active = true;
    setMessages([]);
    setError(null);
    getPackMessages(snapshotId)
      .then((m) => { if (active) setMessages(m); })
      .catch(() => { if (active) setError("Couldn't load the conversation."); });
    return () => { active = false; };
  }, [snapshotId]);

  async function send() {
    const q = draft.trim();
    if (!q || sending) return;
    const refs = attachments.map((a) => a.id);
    setError(null);
    setSending(true);
    setDraft("");
    const optimistic: MessageOut = {
      id: `tmp-${tmpIdRef.current++}`, role: "user", content: q, block_refs: refs, created_at: "",
    };
    setMessages((m) => [...m, optimistic]);
    try {
      const answer = await postPackMessage(snapshotId, { content: q, block_refs: refs });
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
    <aside className={styles.panel} aria-label="Article chat">
      <div className={styles.header}>
        <span className="t-label">Chat</span>
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
      {attachments.length > 0 && (
        <div className={styles.attachments}>
          {attachments.map((a) => (
            <span key={a.id} className={styles.chip}>
              {a.label}
              <button type="button" aria-label={`Remove ${a.label}`} onClick={() => onRemoveAttachment(a.id)}>
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <div className={styles.composer}>
        <textarea
          aria-label="Ask about this article"
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
