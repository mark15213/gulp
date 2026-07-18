"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  createToken,
  getTokens,
  revokeToken,
  type TokenCreatedOut,
  type TokenOut,
} from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import styles from "./TokensSettings.module.css";

// PAT management (spec 2026-07-16 §2): the plaintext is shown exactly once,
// right after creation — after that only the prefix identifies a token.
export function TokensSettings() {
  const [tokens, setTokens] = useState<TokenOut[] | null>(null);
  const [name, setName] = useState("");
  const [fresh, setFresh] = useState<TokenCreatedOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setTokens(await getTokens());
    } catch {
      setError("Couldn't load tokens.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onCreate() {
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setFresh(await createToken(name.trim()));
      setName("");
      await refresh();
    } catch {
      setError("Token creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(id: string) {
    setBusy(true);
    setError(null);
    try {
      await revokeToken(id);
      if (fresh?.id === id) setFresh(null);
      await refresh();
    } catch {
      setError("Revoke failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!tokens) return <p className={styles.muted}>{error ?? "Loading…"}</p>;

  return (
    <div className={styles.root}>
      <h1 className={styles.title}>API tokens</h1>
      <p className={styles.muted}>
        Personal access tokens let local agents (Claude Code, Codex…) reach the
        Gulp MCP endpoint. Treat them like passwords.
      </p>
      {fresh && (
        <div className={styles.freshBox}>
          <p>Copy this token now — it will not be shown again:</p>
          <code className={styles.tokenCode}>{fresh.token}</code>
        </div>
      )}
      <div className={styles.createRow}>
        <input
          className={styles.input}
          placeholder="token name (e.g. laptop)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button onClick={() => void onCreate()} disabled={busy || !name.trim()}>
          Generate
        </Button>
      </div>
      <ul className={styles.list}>
        {tokens.map((t) => (
          <li key={t.id} className={styles.row}>
            <span className={styles.name}>{t.name}</span>
            <code className={styles.prefix}>{t.prefix}…</code>
            <span className={styles.muted}>
              {t.last_used_at
                ? `last used ${new Date(t.last_used_at).toLocaleString()}`
                : "never used"}
            </span>
            <Button onClick={() => void onRevoke(t.id)} disabled={busy}>
              Revoke
            </Button>
          </li>
        ))}
      </ul>
      {error && <p className={styles.error}>{error}</p>}
    </div>
  );
}
