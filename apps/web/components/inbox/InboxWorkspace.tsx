"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { FeedEntry, Snapshot, Subscription } from "@gulp/api-client";
import {
  createSubscription,
  deleteSnapshot,
  deleteSubscription,
  getFeedEntries,
  getInbox,
  getSnapshot,
  getSubscriptions,
  gulpEntry,
  patchSubscription,
  processBatch,
  refreshSubscription,
  setEntryRead,
  setEntrySkipped,
  skipAllSubscription,
  startProcessing,
} from "@gulp/api-client";
import {
  SubscriptionList,
  sameSource,
  type SourceFilter,
} from "@/components/feeds/SubscriptionList";
import { AddFeedDialog } from "@/components/feeds/AddFeedDialog";
import { StageSection } from "./StageSection";
import { EntryRow } from "./EntryRow";
import { SnapshotRow } from "./SnapshotRow";
import { DecisionPane } from "./DecisionPane";
import { STAGES, TERMINAL, isActionable, stageOf, triageOf } from "./stages";
import styles from "./InboxWorkspace.module.css";

const ENTRY_PAGE_SIZE = 50;
const COLLAPSE_KEY = "gulp.inbox.collapsed";
const POLL_MS = 3000;

type Cursor = { kind: "entry" | "snapshot"; id: string };

export function InboxWorkspace({
  initialSubscriptions,
  initialEntries,
  initialEntryCount,
  initialItems,
  initialActionable,
}: {
  initialSubscriptions: Subscription[];
  initialEntries: FeedEntry[];
  initialEntryCount: number;
  initialItems: Snapshot[];
  initialActionable: number;
}) {
  const router = useRouter();
  const [subs, setSubs] = useState(initialSubscriptions);
  const [entries, setEntries] = useState(initialEntries);
  const [entryCount, setEntryCount] = useState(initialEntryCount);
  const [entryPage, setEntryPage] = useState(0);
  const [items, setItems] = useState(initialItems);
  const [actionable, setActionable] = useState(initialActionable);
  const [source, setSource] = useState<SourceFilter>({ kind: "all" });
  const [pendingOnly, setPendingOnly] = useState(true);
  const [selected, setSelected] = useState<Cursor | null>(null);
  const [cursor, setCursor] = useState<Cursor | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [addOpen, setAddOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  // The belt's last frame: ids started on this mount. Session-scoped by
  // construction — a remount forgets them and the items live in the Library.
  const [tracked, setTracked] = useState<Record<string, Snapshot>>({});

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(COLLAPSE_KEY);
      if (raw) setCollapsed(JSON.parse(raw));
    } catch {
      // a corrupt preference shouldn't break the surface
    }
  }, []);

  const toggleSection = useCallback((key: string) => {
    setCollapsed((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try {
        window.localStorage.setItem(COLLAPSE_KEY, JSON.stringify(next));
      } catch {
        // private mode — collapsing still works for this visit
      }
      return next;
    });
  }, []);

  const subId = source.kind === "sub" ? source.id : undefined;

  const reloadEntries = useCallback(
    async (page = 0, only = pendingOnly, filter: SourceFilter = source) => {
      if (filter.kind === "captured") return;
      const out = await getFeedEntries({
        subscriptionId: filter.kind === "sub" ? filter.id : undefined,
        pendingOnly: only,
        limit: ENTRY_PAGE_SIZE,
        offset: page * ENTRY_PAGE_SIZE,
      });
      setEntries(out.items);
      setEntryCount(out.count);
      setEntryPage(page);
    },
    [pendingOnly, source],
  );

  const reloadItems = useCallback(
    async (filter: SourceFilter = source) => {
      const out = await getInbox({
        emittedBy: filter.kind === "sub" ? filter.id : undefined,
        adHocOnly: filter.kind === "captured",
      });
      setItems(out.items);
      setActionable(out.actionable_count);
    },
    [source],
  );

  const reloadSubs = useCallback(async () => {
    setSubs((await getSubscriptions()).items);
  }, []);

  const selectSource = useCallback(
    async (next: SourceFilter) => {
      if (sameSource(next, source)) return;
      setSource(next);
      setSelected(null);
      setCursor(null);
      setChecked(new Set());
      if (next.kind === "captured") setEntries([]);
      await Promise.all([reloadEntries(0, pendingOnly, next), reloadItems(next)]);
    },
    [pendingOnly, reloadEntries, reloadItems, source],
  );

  // ── stage 1 actions ────────────────────────────────────────────────────

  const openEntry = useCallback((entry: FeedEntry) => {
    setSelected({ kind: "entry", id: entry.id });
    setCursor({ kind: "entry", id: entry.id });
    if (!entry.read) {
      // "Seen" only — opening must not remove it from the queue (spec §2).
      setEntries((es) => es.map((e) => (e.id === entry.id ? { ...e, read: true } : e)));
      void setEntryRead(entry.id, true);
    }
  }, []);

  const forward = useCallback(
    async (entry: FeedEntry) => {
      if (!entry.url) return;
      const { snapshot_id } = await gulpEntry(entry.id);
      // Forward moves the row down one section: out of New, into Kept.
      setEntries((es) => es.filter((e) => e.id !== entry.id));
      setEntryCount((c) => Math.max(0, c - 1));
      if (selected?.id === entry.id) setSelected({ kind: "snapshot", id: snapshot_id });
      await Promise.all([reloadItems(), reloadSubs()]);
    },
    [reloadItems, reloadSubs, selected],
  );

  const skip = useCallback(
    async (entry: FeedEntry, skipped: boolean) => {
      setEntries((es) =>
        pendingOnly && skipped
          ? es.filter((e) => e.id !== entry.id)
          : es.map((e) => (e.id === entry.id ? { ...e, skipped, read: e.read || skipped } : e)),
      );
      if (pendingOnly && skipped) {
        setEntryCount((c) => Math.max(0, c - 1));
        if (selected?.id === entry.id) setSelected(null);
      }
      await setEntrySkipped(entry.id, skipped);
      await reloadSubs();
    },
    [pendingOnly, reloadSubs, selected],
  );

  const skipAll = useCallback(async () => {
    if (!subId) return;
    if (!window.confirm("Skip everything undecided in this feed?")) return;
    await skipAllSubscription(subId);
    setSelected(null);
    await Promise.all([reloadEntries(0), reloadSubs()]);
  }, [reloadEntries, reloadSubs, subId]);

  // ── stage 2 actions ────────────────────────────────────────────────────

  const track = useCallback((snapshot: Snapshot) => {
    setTracked((t) => ({ ...t, [snapshot.id]: { ...snapshot, status: "processing" } }));
    setItems((list) => list.filter((i) => i.id !== snapshot.id));
    setActionable((n) => Math.max(0, n - 1));
  }, []);

  const start = useCallback(
    async (snapshot: Snapshot) => {
      track(snapshot);
      try {
        await startProcessing(snapshot.id);
      } catch {
        await reloadItems(); // 409 or transient — the server's view wins
      }
    },
    [reloadItems, track],
  );

  const startChecked = useCallback(async () => {
    const ids = [...checked];
    if (ids.length === 0) return;
    const targets = items.filter((i) => ids.includes(i.id));
    targets.forEach(track);
    setChecked(new Set());
    const out = await processBatch(ids);
    if (out.skipped.length > 0) {
      setTracked((t) => {
        const next = { ...t };
        out.skipped.forEach((s) => delete next[s.id]);
        return next;
      });
      await reloadItems();
    }
  }, [checked, items, reloadItems, track]);

  const removeSnapshot = useCallback(
    async (snapshot: Snapshot) => {
      if (!window.confirm(`Delete "${snapshot.title}"?`)) return;
      await deleteSnapshot(snapshot.id);
      if (selected?.id === snapshot.id) setSelected(null);
      await reloadItems();
    },
    [reloadItems, selected],
  );

  // ── the last frame: poll only what this session started ────────────────

  const trackedRef = useRef(tracked);
  trackedRef.current = tracked;
  const inflightIds = Object.values(tracked)
    .filter((s) => !TERMINAL.has(s.status))
    .map((s) => s.id)
    .sort()
    .join(",");

  useEffect(() => {
    if (!inflightIds) return;
    let cancelled = false;
    const tick = async () => {
      const targets = Object.values(trackedRef.current).filter(
        (s) => !TERMINAL.has(s.status),
      );
      const fresh = await Promise.all(
        targets.map((s) => getSnapshot(s.id).catch(() => null)),
      );
      if (cancelled) return;
      const landed = fresh.filter((s): s is Snapshot => !!s && TERMINAL.has(s.status));
      setTracked((t) => {
        const next = { ...t };
        fresh.forEach((s) => {
          if (!s) return;
          // Only `ready` earns the last frame; anything else goes back to the
          // sections that own it.
          if (TERMINAL.has(s.status) && s.status !== "ready") delete next[s.id];
          else next[s.id] = s;
        });
        return next;
      });
      if (landed.some((s) => s.status !== "ready")) void reloadItems();
    };
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [inflightIds, reloadItems]);

  // The sidebar badge is server-rendered; nudge it when our count moves.
  const lastActionable = useRef(initialActionable);
  useEffect(() => {
    if (lastActionable.current !== actionable) {
      lastActionable.current = actionable;
      router.refresh();
    }
  }, [actionable, router]);

  // ── derived sections ───────────────────────────────────────────────────

  const trackedList = Object.values(tracked);
  const sections = useMemo(() => {
    const kept: Snapshot[] = [];
    const needs: Snapshot[] = [];
    const flight: Snapshot[] = [];
    items.forEach((item) => {
      const stage = stageOf(item.status);
      if (stage === "kept") kept.push(item);
      else if (stage === "needs") needs.push(item);
      else if (stage === "flight") flight.push(item);
    });
    // Tracked items render from our own copy so the row can turn into
    // "Ready · Read →" in place rather than vanishing.
    const trackedIds = new Set(trackedList.map((s) => s.id));
    return {
      kept,
      needs,
      flight: [...trackedList, ...flight.filter((i) => !trackedIds.has(i.id))],
    };
  }, [items, trackedList]);

  const visibleEntries = source.kind === "captured" ? [] : entries;
  const pendingEntries = visibleEntries.filter((e) => triageOf(e) === "pending");

  const flatRows: Cursor[] = useMemo(
    () => [
      ...(collapsed.new ? [] : visibleEntries.map((e) => ({ kind: "entry" as const, id: e.id }))),
      ...(["kept", "needs", "flight"] as const).flatMap((k) =>
        collapsed[k]
          ? []
          : sections[k].map((i) => ({ kind: "snapshot" as const, id: i.id })),
      ),
    ],
    [collapsed, sections, visibleEntries],
  );

  const selectedEntry =
    selected?.kind === "entry" ? (entries.find((e) => e.id === selected.id) ?? null) : null;
  const selectedSnapshot =
    selected?.kind === "snapshot"
      ? (tracked[selected.id] ?? items.find((i) => i.id === selected.id) ?? null)
      : null;

  // ── keyboard: the list is the primary surface (spec §4.3) ──────────────

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;
      const index = cursor ? flatRows.findIndex((r) => r.id === cursor.id) : -1;
      const at = (i: number) =>
        flatRows[Math.max(0, Math.min(flatRows.length - 1, i))] ?? null;
      const current = index >= 0 ? (flatRows[index] ?? null) : null;
      const entryAt = current?.kind === "entry" ? entries.find((e) => e.id === current.id) : null;
      const snapAt =
        current?.kind === "snapshot"
          ? (tracked[current.id] ?? items.find((i) => i.id === current.id))
          : null;

      switch (event.key) {
        case "j":
          if (flatRows.length) setCursor(at(index + 1));
          break;
        case "k":
          if (flatRows.length) setCursor(at(index < 0 ? 0 : index - 1));
          break;
        case "Enter":
          if (current) setSelected(current);
          break;
        case "o":
          if (snapAt) router.push(`/snapshots/${snapAt.id}`);
          else if (entryAt?.url) window.open(entryAt.url, "_blank", "noopener");
          break;
        case "f":
          if (entryAt) void forward(entryAt);
          break;
        case "s":
          if (entryAt) void skip(entryAt, true);
          break;
        case "u":
          if (entryAt?.skipped) void skip(entryAt, false);
          break;
        default:
          return;
      }
      event.preventDefault();
    },
    [cursor, entries, flatRows, forward, items, router, skip, tracked],
  );

  const capturedCount = source.kind === "captured" ? items.length : 0;
  const totalPages = Math.max(1, Math.ceil(entryCount / ENTRY_PAGE_SIZE));

  return (
    <div className={styles.workspace}>
      <SubscriptionList
        subscriptions={subs}
        selected={source}
        capturedCount={capturedCount}
        onSelect={selectSource}
        onToggleMute={async (sub) => {
          await patchSubscription(sub.id, { muted: !sub.muted });
          await reloadSubs();
        }}
        onDelete={async (sub) => {
          if (!window.confirm(`Unsubscribe from "${sub.title}"? Its entries are removed.`))
            return;
          await deleteSubscription(sub.id);
          await selectSource({ kind: "all" });
          await reloadSubs();
        }}
        onRefresh={async (sub) => {
          await refreshSubscription(sub.id);
          window.setTimeout(() => {
            void reloadSubs();
            void reloadEntries(entryPage);
          }, 2500);
        }}
        onAdd={() => setAddOpen(true)}
      />

      {/* Focusable region so j/k/f/s/u reach the list without a roving
          tabindex on every row; each row keeps its own real controls. */}
      <div
        className={styles.stages}
        role="region"
        aria-label="Intake stages"
        tabIndex={0}
        onKeyDown={onKeyDown}
      >
        {STAGES.map((stage) => {
          if (stage.key === "new") {
            if (source.kind === "captured") return null;
            return (
              <StageSection
                key={stage.key}
                label={stage.label}
                question={stage.question}
                count={pendingEntries.length}
                collapsed={!!collapsed.new}
                onToggle={() => toggleSection("new")}
                empty={pendingOnly ? stage.empty : "No entries yet."}
                controls={
                  <span className={styles.controls}>
                    {subId && (
                      <button type="button" className={styles.toggle} onClick={skipAll}>
                        Skip all
                      </button>
                    )}
                    <button
                      type="button"
                      className={`${styles.toggle} ${pendingOnly ? styles.toggleOn : ""}`}
                      aria-pressed={pendingOnly}
                      onClick={() => {
                        const next = !pendingOnly;
                        setPendingOnly(next);
                        void reloadEntries(0, next);
                      }}
                    >
                      {pendingOnly ? "Pending" : "All"}
                    </button>
                  </span>
                }
                footer={
                  totalPages > 1 ? (
                    <div className={`t-data ${styles.pagination}`}>
                      <button
                        type="button"
                        disabled={entryPage === 0}
                        onClick={() => void reloadEntries(entryPage - 1)}
                      >
                        ← Previous
                      </button>
                      <span aria-live="polite">
                        Page {entryPage + 1} of {totalPages} · {entryCount}
                      </span>
                      <button
                        type="button"
                        disabled={entryPage + 1 >= totalPages}
                        onClick={() => void reloadEntries(entryPage + 1)}
                      >
                        Next →
                      </button>
                    </div>
                  ) : undefined
                }
              >
                {visibleEntries.map((entry) => (
                  <EntryRow
                    key={entry.id}
                    entry={entry}
                    selected={selected?.kind === "entry" && selected.id === entry.id}
                    cursor={cursor?.kind === "entry" && cursor.id === entry.id}
                    onSelect={() => openEntry(entry)}
                    onForward={() => void forward(entry)}
                    onSkip={(next) => void skip(entry, next)}
                  />
                ))}
              </StageSection>
            );
          }

          const rows = sections[stage.key as "kept" | "needs" | "flight"];
          return (
            <StageSection
              key={stage.key}
              label={stage.label}
              question={stage.question}
              count={rows.length}
              collapsed={!!collapsed[stage.key]}
              onToggle={() => toggleSection(stage.key)}
              empty={stage.empty}
              footer={
                stage.key === "kept" && checked.size > 0 ? (
                  <div className={styles.batchBar}>
                    <span className="t-data">{checked.size} selected</span>
                    <button
                      type="button"
                      className={`${styles.action} ${styles.act}`}
                      onClick={startChecked}
                    >
                      ▶ Start {checked.size}
                    </button>
                  </div>
                ) : undefined
              }
            >
              {rows.map((item) => (
                <SnapshotRow
                  key={item.id}
                  item={item}
                  stage={stage.key}
                  done={stage.key === "flight" && item.status === "ready"}
                  selected={selected?.kind === "snapshot" && selected.id === item.id}
                  cursor={cursor?.kind === "snapshot" && cursor.id === item.id}
                  checked={checked.has(item.id)}
                  onCheck={
                    stage.key === "kept"
                      ? (on) =>
                          setChecked((prev) => {
                            const next = new Set(prev);
                            if (on) next.add(item.id);
                            else next.delete(item.id);
                            return next;
                          })
                      : undefined
                  }
                  onSelect={() => {
                    setSelected({ kind: "snapshot", id: item.id });
                    setCursor({ kind: "snapshot", id: item.id });
                  }}
                  onStart={
                    stage.key === "kept" || item.status === "needs_attention"
                      ? () => void start(item)
                      : undefined
                  }
                  onExport={
                    stage.key === "kept" || stage.key === "needs"
                      ? () => router.push(`/snapshots/${item.id}`)
                      : undefined
                  }
                  onDelete={stage.key !== "flight" ? () => void removeSnapshot(item) : undefined}
                />
              ))}
            </StageSection>
          );
        })}
      </div>

      <DecisionPane
        entry={selectedEntry}
        snapshot={selectedSnapshot}
        done={!!selectedSnapshot && !!tracked[selectedSnapshot.id] && selectedSnapshot.status === "ready"}
        onForward={(entry) => void forward(entry)}
        onSkip={(entry, next) => void skip(entry, next)}
        onStart={(snapshot) => void start(snapshot)}
      />

      <AddFeedDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSubmit={async (feedUrl, title) => {
          await createSubscription({ feed_url: feedUrl, title });
          await reloadSubs();
        }}
      />
    </div>
  );
}

export { isActionable };
