"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  getPackMessages,
  streamPackMessage,
  type MessageOut,
} from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import { IconButton } from "@/components/ui/IconButton";
import { IconClose } from "@/components/ui/icons";
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
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [streamText, setStreamText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tmpIdRef = useRef(0);

  useEffect(() => {
    let active = true;
    setMessages([]);
    setError(null);
    setLoading(true);
    getPackMessages(snapshotId)
      .then((m) => {
        if (active) setMessages(m);
      })
      .catch(() => {
        if (active) setError("Couldn't load the conversation.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [snapshotId]);

  const ERROR_COPY: Record<string, string> = {
    llm_not_configured: "Add an AI provider key in Settings → AI models first.",
    llm_key_invalid: "Your AI key was rejected — check Settings → AI models.",
    llm_rate_limited: "The provider rate-limited this key — try again shortly.",
  };

  async function send() {
    const q = draft.trim();
    if (!q || sending) return;
    const refs = attachments.map((a) => a.id);
    setError(null);
    setSending(true);
    setDraft("");
    const optimistic: MessageOut = {
      id: `tmp-${tmpIdRef.current++}`,
      role: "user",
      content: q,
      block_refs: refs,
      created_at: "",
    };
    setMessages((m) => [...m, optimistic]);
    let failed: string | null = null;
    try {
      let acc = "";
      for await (const ev of streamPackMessage(snapshotId, {
        content: q,
        block_refs: refs,
      })) {
        if (ev.type === "delta") {
          acc += ev.text;
          setStreamText(acc);
        } else if (ev.type === "done") {
          setMessages((m) => [...m, ev.message]);
        } else {
          failed = ERROR_COPY[ev.code] ?? "Couldn't send — try again.";
        }
      }
    } catch {
      failed = "Couldn't send — try again.";
    } finally {
      setStreamText(null);
      setSending(false);
    }
    if (failed) {
      setMessages((m) => m.filter((x) => x.id !== optimistic.id));
      setDraft(q);
      setError(failed);
    }
  }

  return (
    <aside className={styles.panel} aria-label="Article chat">
      <div className={styles.header}>
        <span className="t-label">Chat</span>
        <IconButton
          label="Close chat"
          className={styles.close}
          onClick={onClose}
        >
          <IconClose />
        </IconButton>
      </div>
      <div
        className={styles.messages}
        role="log"
        aria-label="Conversation"
        aria-live="polite"
      >
        {loading && (
          <div className={styles.state} role="status">
            Loading conversation…
          </div>
        )}
        {!loading && !error && messages.length === 0 && !sending && (
          <div className={styles.state}>
            <p className={styles.stateTitle}>Start a conversation</p>
            <p>
              Ask a question about this article or attach a passage for context.
            </p>
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`${styles.message} ${m.role === "user" ? styles.user : styles.assistant}`}
          >
            {m.content}
          </div>
        ))}
        {streamText !== null && streamText !== "" && (
          <div className={`${styles.message} ${styles.assistant}`}>
            {streamText}
          </div>
        )}
        {sending && !streamText && (
          <div className={styles.thinking}>Thinking…</div>
        )}
        {error && (
          <div className={styles.err} role="alert">
            {error}
          </div>
        )}
      </div>
      <div className={styles.composer}>
        {attachments.length > 0 && (
          <div
            className={styles.attachments}
            aria-label="Attached article passages"
          >
            <span className={`t-label ${styles.attachmentsLabel}`}>
              Context
            </span>
            <div className={styles.attachmentList}>
              {attachments.map((a) => (
                <span key={a.id} className={styles.chip}>
                  <span className={styles.chipLabel}>{a.label}</span>
                  <button
                    type="button"
                    className={styles.chipRemove}
                    aria-label={`Remove ${a.label}`}
                    onClick={() => onRemoveAttachment(a.id)}
                  >
                    <IconClose />
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}
        <textarea
          aria-label="Ask about this article"
          className={styles.input}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="Ask about this article…"
          rows={3}
          disabled={loading || sending}
        />
        <div className={styles.composerFooter}>
          <span className={styles.shortcut}>Ctrl / ⌘ + Enter to send</span>
          <Button
            variant="primary"
            className={styles.send}
            onClick={send}
            disabled={loading || sending || !draft.trim()}
          >
            Send
          </Button>
        </div>
      </div>
    </aside>
  );
}
