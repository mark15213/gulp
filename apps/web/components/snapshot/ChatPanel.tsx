"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  getLLMSettings,
  getPackMessages,
  streamPackMessage,
  type LLMSettingsOut,
  type MessageOut,
} from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import { IconButton } from "@/components/ui/IconButton";
import { IconClose } from "@/components/ui/icons";
import type { ChatAttachment } from "./ReaderChatContext";
import { Md } from "./Md";
import styles from "./ChatPanel.module.css";

const MODEL_STORAGE_KEY = "chat:selectedModel";
const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  deepseek: "DeepSeek",
  qwen: "Qwen",
};

type ModelChoice = {
  key: string;
  provider: string;
  model: string;
  label: string;
};

function availableModels(settings: LLMSettingsOut): ModelChoice[] {
  const configured = new Set(settings.credentials.map((item) => item.provider));
  return settings.catalog.flatMap((provider) =>
    configured.has(provider.provider)
      ? provider.models.map((model) => ({
          key: `${provider.provider}:${model.id}`,
          provider: provider.provider,
          model: model.id,
          label: model.label,
        }))
      : [],
  );
}

export function ChatPanel({
  snapshotId,
  attachments,
  onRemoveAttachment,
  onClearAttachments,
  onOpenReference,
  onClose,
}: {
  snapshotId: string;
  attachments: ChatAttachment[];
  onRemoveAttachment: (id: string) => void;
  onClearAttachments?: () => void;
  onOpenReference?: (id: string) => void;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [streamText, setStreamText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelChoices, setModelChoices] = useState<ModelChoice[]>([]);
  const [selectedModelKey, setSelectedModelKey] = useState("");
  const [modelsLoading, setModelsLoading] = useState(true);
  const tmpIdRef = useRef(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const selectedModel = modelChoices.find(
    (choice) => choice.key === selectedModelKey,
  );

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

  useEffect(() => {
    let active = true;
    setModelsLoading(true);
    setModelError(null);
    getLLMSettings()
      .then((settings) => {
        if (!active) return;
        const choices = availableModels(settings);
        const saved = localStorage.getItem(MODEL_STORAGE_KEY);
        const legacyDefault =
          settings.default_provider && settings.default_model
            ? `${settings.default_provider}:${settings.default_model}`
            : null;
        const initial =
          choices.find((choice) => choice.key === saved) ??
          choices.find((choice) => choice.key === legacyDefault) ??
          choices[0];
        setModelChoices(choices);
        setSelectedModelKey(initial?.key ?? "");
      })
      .catch(() => {
        if (active) setModelError("Couldn't load your available AI models.");
      })
      .finally(() => {
        if (active) setModelsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!loading && !modelsLoading && selectedModel) {
      inputRef.current?.focus();
    }
  }, [loading, modelsLoading, selectedModel]);

  useEffect(() => {
    if (!loading) bottomRef.current?.scrollIntoView?.({ block: "end" });
  }, [error, loading, messages, sending, streamText]);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const ERROR_COPY: Record<string, string> = {
    llm_not_configured:
      "Add an AI provider key in Settings → AI providers first.",
    llm_key_invalid:
      "Your AI key was rejected — check Settings → AI providers.",
    llm_rate_limited: "The provider rate-limited this key — try again shortly.",
  };

  async function send() {
    const q = draft.trim();
    if (!q || sending || !selectedModel) return;
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
    let completed = false;
    try {
      let acc = "";
      for await (const ev of streamPackMessage(snapshotId, {
        content: q,
        block_refs: refs,
        provider: selectedModel.provider,
        model: selectedModel.model,
      })) {
        if (ev.type === "delta") {
          acc += ev.text;
          setStreamText(acc);
        } else if (ev.type === "done") {
          setMessages((m) => [...m, ev.message]);
          completed = true;
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
    } else if (completed) {
      onClearAttachments?.();
    }
  }

  return (
    <aside className={styles.panel} aria-label="Article chat">
      <div className={styles.header}>
        <div className={styles.headerCopy}>
          <span className={styles.headerTitle}>Discuss this article</span>
          <span className={styles.saved}>Saved automatically</span>
        </div>
        <div className={styles.headerActions}>
          <select
            aria-label="AI model"
            className={styles.modelSelect}
            value={selectedModelKey}
            disabled={modelsLoading || sending || modelChoices.length === 0}
            onChange={(event) => {
              setSelectedModelKey(event.target.value);
              localStorage.setItem(MODEL_STORAGE_KEY, event.target.value);
            }}
          >
            {modelsLoading && <option value="">Loading models…</option>}
            {!modelsLoading && modelChoices.length === 0 && (
              <option value="">No model configured</option>
            )}
            {[...new Set(modelChoices.map((choice) => choice.provider))].map(
              (provider) => (
                <optgroup
                  key={provider}
                  label={PROVIDER_LABELS[provider] ?? provider}
                >
                  {modelChoices
                    .filter((choice) => choice.provider === provider)
                    .map((choice) => (
                      <option key={choice.key} value={choice.key}>
                        {choice.label}
                      </option>
                    ))}
                </optgroup>
              ),
            )}
          </select>
          <IconButton
            label="Close chat"
            className={styles.close}
            onClick={onClose}
          >
            <IconClose />
          </IconButton>
        </div>
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
            <div className={styles.messageBody}>
              {m.role === "assistant" ? <Md>{m.content}</Md> : m.content}
            </div>
            {m.block_refs.length > 0 && (
              <div
                className={styles.messageRefs}
                aria-label={
                  m.role === "user" ? "Attached context" : "Answer sources"
                }
              >
                {m.block_refs.map((ref, index) => (
                  <button
                    key={ref}
                    type="button"
                    className={styles.messageRef}
                    onClick={() => onOpenReference?.(ref)}
                    disabled={!onOpenReference}
                  >
                    {m.role === "user" ? "Context" : "Passage"} {index + 1}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {streamText !== null && streamText !== "" && (
          <div className={`${styles.message} ${styles.assistant}`}>
            <div className={styles.messageBody}>
              <Md>{streamText}</Md>
            </div>
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
        <div ref={bottomRef} aria-hidden="true" />
      </div>
      <div className={styles.composer}>
        {modelError && (
          <div className={styles.modelNotice} role="alert">
            {modelError}
          </div>
        )}
        {!modelsLoading && !modelError && modelChoices.length === 0 && (
          <div className={styles.modelNotice}>
            Add a provider key in{" "}
            <Link href="/settings/ai">Settings → AI providers</Link> to start
            chatting.
          </div>
        )}
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
          ref={inputRef}
          aria-label="Ask about this article"
          className={styles.input}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="Ask about this article…"
          rows={3}
          disabled={
            loading || sending || modelsLoading || selectedModel === undefined
          }
        />
        <div className={styles.composerFooter}>
          <span className={styles.shortcut}>
            Enter to send · Shift + Enter for a new line
          </span>
          <Button
            variant="primary"
            className={styles.send}
            onClick={send}
            disabled={
              loading ||
              sending ||
              modelsLoading ||
              selectedModel === undefined ||
              !draft.trim()
            }
          >
            Send
          </Button>
        </div>
      </div>
    </aside>
  );
}
