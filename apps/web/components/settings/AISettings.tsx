"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  deleteLLMCredential,
  getLLMSettings,
  putLLMCredential,
  putLLMDefault,
  type LLMSettingsOut,
} from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import styles from "./AISettings.module.css";

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  deepseek: "DeepSeek",
  qwen: "Qwen",
};

export function AISettings() {
  const [data, setData] = useState<LLMSettingsOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [defProvider, setDefProvider] = useState("");
  const [defModel, setDefModel] = useState("");

  const refresh = useCallback(async () => {
    try {
      const s = await getLLMSettings();
      setData(s);
      setDefProvider(s.default_provider ?? "");
      setDefModel(s.default_model ?? "");
    } catch {
      setError("Couldn't load AI settings.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function act(fn: () => Promise<void>, failMsg: string) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(
        e instanceof Error && e.message === "invalid_key"
          ? "That key was rejected by the provider."
          : failMsg,
      );
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return <p className={styles.muted}>{error ?? "Loading…"}</p>;
  }

  const configured = new Set(data.credentials.map((c) => c.provider));
  const masked = new Map(data.credentials.map((c) => [c.provider, c.masked_key]));
  const models = data.catalog.find((c) => c.provider === defProvider)?.models ?? [];

  return (
    <div className={styles.root}>
      <Link href="/settings" className={styles.backLink}>
        ← Settings
      </Link>
      <h1 className={styles.title}>AI models</h1>
      <p className={styles.muted}>
        Bring your own API keys. Gulp calls providers with your key and never
        shows it again after saving.
      </p>
      {error && <p className={styles.error}>{error}</p>}
      {data.catalog.map((p) => (
        <section key={p.provider} className={styles.card}>
          <header className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>{PROVIDER_LABELS[p.provider] ?? p.provider}</h2>
            <span className={styles.caps}>{p.capabilities.join(" · ")}</span>
          </header>
          {configured.has(p.provider) ? (
            <div className={styles.row}>
              <code className={styles.mask}>{masked.get(p.provider)}</code>
              <Button
                disabled={busy}
                onClick={() =>
                  void act(() => deleteLLMCredential(p.provider), "Couldn't delete the key.")
                }
              >
                Delete key
              </Button>
            </div>
          ) : (
            <div className={styles.row}>
              <input
                className={styles.input}
                type="password"
                placeholder="API key"
                value={drafts[p.provider] ?? ""}
                onChange={(e) =>
                  setDrafts((d) => ({ ...d, [p.provider]: e.target.value }))
                }
              />
              <Button
                disabled={busy || !(drafts[p.provider] ?? "").trim()}
                onClick={() =>
                  void act(async () => {
                    await putLLMCredential(p.provider, (drafts[p.provider] ?? "").trim());
                    setDrafts((d) => ({ ...d, [p.provider]: "" }));
                  }, "Couldn't save the key.")
                }
              >
                Save key
              </Button>
            </div>
          )}
        </section>
      ))}
      <section className={styles.card}>
        <h2 className={styles.cardTitle}>Default model</h2>
        <div className={styles.row}>
          <label className={styles.label} htmlFor="def-provider">
            Default provider
          </label>
          <select
            id="def-provider"
            className={styles.select}
            value={defProvider}
            onChange={(e) => {
              setDefProvider(e.target.value);
              setDefModel("");
            }}
          >
            <option value="">—</option>
            {[...configured].map((p) => (
              <option key={p} value={p}>
                {PROVIDER_LABELS[p] ?? p}
              </option>
            ))}
          </select>
          <label className={styles.label} htmlFor="def-model">
            Default model
          </label>
          <select
            id="def-model"
            className={styles.select}
            value={defModel}
            onChange={(e) => setDefModel(e.target.value)}
          >
            <option value="">—</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
          <Button
            variant="primary"
            disabled={busy || !defProvider || !defModel}
            onClick={() =>
              void act(() => putLLMDefault(defProvider, defModel), "Couldn't save the default.")
            }
          >
            Save default
          </Button>
        </div>
        {configured.size === 0 && (
          <p className={styles.muted}>Add a key first to pick a default.</p>
        )}
      </section>
    </div>
  );
}
