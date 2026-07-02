"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getInbox, getLibrary } from "@gulp/api-client";
import { filterEntries, type SearchEntry } from "@/lib/search";
import { IconSearch } from "@/components/ui/icons";
import sidebar from "./Sidebar.module.css";
import styles from "./SearchCommand.module.css";

const PAGES: SearchEntry[] = [
  { id: "page-today", title: "Today", tags: [], href: "/", kind: "page" },
  { id: "page-inbox", title: "Inbox", tags: [], href: "/inbox", kind: "page" },
  { id: "page-library", title: "Library", tags: [], href: "/library", kind: "page" },
];

// ⌘K command palette (docs/03 §5.2). Corpus = static pages + every snapshot
// in Inbox and Library, fetched fresh on open.
export function SearchCommand() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [snapshots, setSnapshots] = useState<SearchEntry[]>([]);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    let cancelled = false;
    Promise.all([getLibrary(), getInbox()])
      .then(([library, inbox]) => {
        if (cancelled) return;
        setSnapshots(
          [...library.items, ...inbox.items].map((s) => ({
            id: s.id,
            title: s.title,
            tags: s.tags,
            href: `/snapshots/${s.id}`,
            kind: "snapshot" as const,
          })),
        );
      })
      .catch(() => setSnapshots([]));
    return () => {
      cancelled = true;
    };
  }, [open]);

  const results = useMemo(
    () => filterEntries([...PAGES, ...snapshots], query),
    [snapshots, query],
  );

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  const onInputKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      go(results[active].href);
    }
  };

  return (
    <>
      <button type="button" className={sidebar.search} onClick={() => setOpen(true)}>
        <IconSearch className={sidebar.searchIcon} />
        <span>Search</span>
        <kbd className={sidebar.kbd}>⌘K</kbd>
      </button>

      {open && (
        <div className={styles.overlay} onClick={() => setOpen(false)}>
          <div
            className={styles.panel}
            role="dialog"
            aria-label="Search"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.inputRow}>
              <IconSearch className={styles.inputIcon} />
              <input
                autoFocus
                className={styles.input}
                placeholder="Search snapshots, tags, pages…"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
                onKeyDown={onInputKey}
              />
              <kbd className={sidebar.kbd}>esc</kbd>
            </div>
            <ul className={styles.results} role="listbox" aria-label="Results">
              {results.map((r, i) => (
                <li key={r.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={i === active}
                    className={`${styles.result} ${i === active ? styles.resultActive : ""}`}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => go(r.href)}
                  >
                    <span className={styles.resultTitle}>{r.title}</span>
                    <span className={styles.resultKind}>
                      {r.kind === "page" ? "Page" : "Snapshot"}
                    </span>
                  </button>
                </li>
              ))}
              {results.length === 0 && <li className={styles.emptyRow}>No matches</li>}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}
