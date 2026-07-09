"use client";

import React, { useState } from "react";
import type { CatalogRoute } from "@gulp/api-client";
import { createSubscription, searchCatalog } from "@gulp/api-client";
import { STARTER_SOURCES } from "./starters";
import styles from "./DiscoverSearch.module.css";

// Paste box + catalog search + starter grid. Subscribing goes through the
// same normalizing endpoint regardless of which surface the address came from.
export function DiscoverSearch() {
  const [paste, setPaste] = useState("");
  const [pasteState, setPasteState] = useState<"idle" | "busy" | "added" | "error">("idle");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CatalogRoute[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [added, setAdded] = useState<Set<string>>(new Set());

  const subscribe = async (feedUrl: string, title?: string | null) => {
    await createSubscription({ feed_url: feedUrl, title: title ?? null });
    setAdded((s) => new Set(s).add(feedUrl));
  };

  const submitPaste = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasteState("busy");
    try {
      await subscribe(paste.trim());
      setPasteState("added");
      setPaste("");
    } catch {
      setPasteState("error");
    }
  };

  const submitSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setSearching(true);
    try {
      setResults((await searchCatalog(query)).items);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className={styles.discover}>
      <form className={styles.pasteRow} onSubmit={submitPaste}>
        <input
          className={styles.input}
          placeholder="Subscribe directly: rsshub://ns/path, /ns/path, or https://…"
          value={paste}
          onChange={(e) => {
            setPaste(e.target.value);
            setPasteState("idle");
          }}
        />
        <button type="submit" className={styles.primary} disabled={!paste.trim() || pasteState === "busy"}>
          {pasteState === "busy" ? "Adding…" : "Subscribe"}
        </button>
      </form>
      {pasteState === "added" && <p className={styles.ok}>Added ✓ — see it on Feeds.</p>}
      {pasteState === "error" && (
        <p className={styles.error}>Could not add — check the address.</p>
      )}

      <form className={styles.searchRow} onSubmit={submitSearch}>
        <input
          className={styles.input}
          placeholder="Search the RSSHub catalog (e.g. github, 少数派, podcast)…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" className={styles.secondary} disabled={searching}>
          {searching ? "Searching…" : "Search"}
        </button>
      </form>

      {results !== null && (
        <section className={styles.section} aria-label="Catalog results">
          <h2 className={styles.sectionTitle}>
            Catalog {results.length > 0 ? `· ${results.length} routes` : "· no matches"}
          </h2>
          <ul className={styles.grid}>
            {results.map((r) => (
              <li key={`${r.namespace}${r.route_path}`} className={styles.card}>
                <div className={styles.cardHead}>
                  <span className={styles.ns}>{r.namespace_name}</span>
                  {r.require_config && (
                    <span className={styles.badge} title="This route needs credentials configured on your RSSHub instance">
                      needs config
                    </span>
                  )}
                </div>
                <p className={styles.routeName}>{r.route_name ?? r.route_path}</p>
                <code className={`t-data ${styles.path}`}>{r.route_path}</code>
                {r.example && (
                  <button
                    type="button"
                    className={styles.example}
                    title="Prefill the subscribe box with this example"
                    onClick={() => {
                      setPaste(r.example ?? "");
                      setPasteState("idle");
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                  >
                    {r.example}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className={styles.section} aria-label="Starter sources">
        <h2 className={styles.sectionTitle}>Starter sources</h2>
        <ul className={styles.grid}>
          {STARTER_SOURCES.map((s) => (
            <li key={s.feedUrl} className={styles.card}>
              <div className={styles.cardHead}>
                <span className={styles.ns}>{s.title}</span>
              </div>
              <p className={styles.routeName}>{s.note}</p>
              <code className={`t-data ${styles.path}`}>{s.feedUrl}</code>
              <button
                type="button"
                className={styles.subscribe}
                disabled={added.has(s.feedUrl)}
                onClick={() => void subscribe(s.feedUrl, s.title)}
              >
                {added.has(s.feedUrl) ? "Added ✓" : "Subscribe"}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
