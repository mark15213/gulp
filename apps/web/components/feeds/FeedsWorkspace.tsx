"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import type { FeedEntry, Subscription } from "@gulp/api-client";
import {
  createSubscription,
  deleteSubscription,
  getFeedEntries,
  getSnapshot,
  getSubscriptions,
  gulpEntry,
  patchSubscription,
  readAllSubscription,
  refreshSubscription,
  setEntryRead,
} from "@gulp/api-client";
import { SubscriptionList } from "./SubscriptionList";
import { EntryList } from "./EntryList";
import { EntryReader } from "./EntryReader";
import { AddFeedDialog } from "./AddFeedDialog";
import styles from "./FeedsWorkspace.module.css";

// Snapshot statuses that no longer change on their own — stop polling once reached.
const TERMINAL_STATUS = new Set(["ready", "exported", "needs_attention"]);
const ENTRY_PAGE_SIZE = 50;

// Three panes: subscriptions | entries | reader. Selection is client state;
// mutations call the api-client then refetch the affected list.
export function FeedsWorkspace({
  initialSubscriptions,
  initialEntries,
  initialEntryCount,
}: {
  initialSubscriptions: Subscription[];
  initialEntries: FeedEntry[];
  initialEntryCount: number;
}) {
  const [subs, setSubs] = useState(initialSubscriptions);
  const [entries, setEntries] = useState(initialEntries);
  const [entryCount, setEntryCount] = useState(initialEntryCount);
  const [entryPage, setEntryPage] = useState(0);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [selectedSubId, setSelectedSubId] = useState<string | null>(null);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [addOpen, setAddOpen] = useState(false);

  const refreshSubs = useCallback(async () => {
    setSubs((await getSubscriptions()).items);
  }, []);

  const refreshEntries = useCallback(
    async (
      subId: string | null = selectedSubId,
      unread: boolean = unreadOnly,
      page: number = entryPage,
    ) => {
      setEntriesLoading(true);
      try {
        const out = await getFeedEntries({
          subscriptionId: subId ?? undefined,
          unreadOnly: unread,
          limit: ENTRY_PAGE_SIZE,
          offset: page * ENTRY_PAGE_SIZE,
        });
        setEntries(out.items);
        setEntryCount(out.count);
        setEntryPage(page);
      } finally {
        setEntriesLoading(false);
      }
    },
    [entryPage, selectedSubId, unreadOnly],
  );

  const selectSub = useCallback(
    async (subId: string | null) => {
      setSelectedSubId(subId);
      setSelectedEntryId(null);
      await refreshEntries(subId, unreadOnly, 0);
    },
    [refreshEntries, unreadOnly],
  );

  const selectEntry = useCallback(
    (entryId: string) => {
      setSelectedEntryId(entryId);
      const entry = entries.find((e) => e.id === entryId);
      if (entry && !entry.read) {
        // reader convention: opening marks read (unread toggle undoes it)
        setEntries((es) =>
          es.map((e) => (e.id === entryId ? { ...e, read: true } : e)),
        );
        setSubs((ss) =>
          ss.map((s) =>
            s.id === entry.subscription_id
              ? { ...s, unread_count: Math.max(0, s.unread_count - 1) }
              : s,
          ),
        );
        void setEntryRead(entryId, true);
      }
    },
    [entries],
  );

  const toggleMute = useCallback(
    async (sub: Subscription) => {
      await patchSubscription(sub.id, { muted: !sub.muted });
      await refreshSubs();
    },
    [refreshSubs],
  );

  const removeSub = useCallback(
    async (sub: Subscription) => {
      if (
        !window.confirm(
          `Unsubscribe from "${sub.title}"? Its entries are removed.`,
        )
      )
        return;
      await deleteSubscription(sub.id);
      if (selectedSubId === sub.id) {
        setSelectedSubId(null);
        setSelectedEntryId(null);
      }
      await Promise.all([refreshSubs(), refreshEntries(null, unreadOnly, 0)]);
    },
    [refreshEntries, refreshSubs, selectedSubId, unreadOnly],
  );

  const refreshOne = useCallback(
    async (sub: Subscription) => {
      await refreshSubscription(sub.id);
      // the fetch is async on the worker; give it a beat then refresh both lists
      window.setTimeout(() => {
        void refreshSubs();
        void refreshEntries();
      }, 2500);
    },
    [refreshEntries, refreshSubs],
  );

  const markAllRead = useCallback(async () => {
    if (!selectedSubId) return;
    await readAllSubscription(selectedSubId);
    setSelectedEntryId(null);
    await Promise.all([
      refreshSubs(),
      refreshEntries(selectedSubId, unreadOnly, 0),
    ]);
  }, [refreshEntries, refreshSubs, selectedSubId, unreadOnly]);

  const toggleUnreadOnly = useCallback(async () => {
    const next = !unreadOnly;
    setUnreadOnly(next);
    setSelectedEntryId(null);
    await refreshEntries(selectedSubId, next, 0);
  }, [refreshEntries, selectedSubId, unreadOnly]);

  const changeEntryPage = useCallback(
    async (nextPage: number) => {
      if (nextPage < 0 || entriesLoading) return;
      setSelectedEntryId(null);
      await refreshEntries(selectedSubId, unreadOnly, nextPage);
    },
    [entriesLoading, refreshEntries, selectedSubId, unreadOnly],
  );

  const onGulp = useCallback(async (entry: FeedEntry) => {
    const { snapshot_id, status } = await gulpEntry(entry.id);
    setEntries((es) =>
      es.map((e) =>
        e.id === entry.id
          ? {
              ...e,
              promoted_source_id: snapshot_id,
              promoted_status: status,
              read: true,
            }
          : e,
      ),
    );
  }, []);

  const onToggleRead = useCallback(async (entry: FeedEntry) => {
    const next = !entry.read;
    setEntries((es) =>
      es.map((e) => (e.id === entry.id ? { ...e, read: next } : e)),
    );
    setSubs((ss) =>
      ss.map((s) =>
        s.id === entry.subscription_id
          ? {
              ...s,
              unread_count: Math.max(0, s.unread_count + (next ? -1 : 1)),
            }
          : s,
      ),
    );
    await setEntryRead(entry.id, next);
  }, []);

  const onAdd = useCallback(
    async (feedUrl: string, title: string | null) => {
      await createSubscription({ feed_url: feedUrl, title });
      await refreshSubs();
    },
    [refreshSubs],
  );

  // Live-follow forwarded entries: poll each promoted snapshot until it reaches a
  // terminal status, so the reader flips Processing… -> In library on its own.
  // Runs only while /feeds is mounted; a stuck worker just keeps a cheap 3s GET
  // going until the user navigates away.
  const entriesRef = useRef(entries);
  entriesRef.current = entries;
  const inflightKey = entries
    .filter(
      (e) =>
        e.promoted_source_id && !TERMINAL_STATUS.has(e.promoted_status ?? ""),
    )
    .map((e) => e.promoted_source_id)
    .sort()
    .join(",");
  useEffect(() => {
    if (!inflightKey) return;
    let cancelled = false;
    const tick = async () => {
      const targets = entriesRef.current.filter(
        (e) =>
          e.promoted_source_id && !TERMINAL_STATUS.has(e.promoted_status ?? ""),
      );
      const results = await Promise.all(
        targets.map(async (e) => {
          try {
            const snap = await getSnapshot(e.promoted_source_id as string);
            return { id: e.id, status: snap.status };
          } catch {
            return null;
          }
        }),
      );
      if (cancelled) return;
      setEntries((es) => {
        let changed = false;
        const next = es.map((e) => {
          const hit = results.find((r) => r && r.id === e.id);
          if (hit && hit.status !== e.promoted_status) {
            changed = true;
            return { ...e, promoted_status: hit.status };
          }
          return e;
        });
        return changed ? next : es;
      });
    };
    const id = window.setInterval(tick, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [inflightKey]);

  const selectedEntry = entries.find((e) => e.id === selectedEntryId) ?? null;
  const selectedSub = subs.find((s) => s.id === selectedSubId) ?? null;

  return (
    <div className={styles.workspace}>
      <SubscriptionList
        subscriptions={subs}
        selectedId={selectedSubId}
        onSelect={selectSub}
        onToggleMute={toggleMute}
        onDelete={removeSub}
        onRefresh={refreshOne}
        onAdd={() => setAddOpen(true)}
      />
      <EntryList
        entries={entries}
        title={selectedSub?.title ?? "All entries"}
        selectedId={selectedEntryId}
        onSelect={selectEntry}
        unreadOnly={unreadOnly}
        onToggleUnreadOnly={toggleUnreadOnly}
        onMarkAllRead={selectedSubId ? markAllRead : undefined}
        page={entryPage}
        pageSize={ENTRY_PAGE_SIZE}
        totalCount={entryCount}
        loading={entriesLoading}
        onPreviousPage={() => void changeEntryPage(entryPage - 1)}
        onNextPage={() => void changeEntryPage(entryPage + 1)}
      />
      <EntryReader
        entry={selectedEntry}
        onGulp={onGulp}
        onToggleRead={onToggleRead}
      />
      <AddFeedDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSubmit={onAdd}
      />
    </div>
  );
}
