"use client";

import React, { useCallback, useState } from "react";
import type { FeedEntry, Subscription } from "@gulp/api-client";
import {
  createSubscription,
  deleteSubscription,
  getFeedEntries,
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

// Three panes: subscriptions | entries | reader. Selection is client state;
// mutations call the api-client then refetch the affected list.
export function FeedsWorkspace({
  initialSubscriptions,
  initialEntries,
}: {
  initialSubscriptions: Subscription[];
  initialEntries: FeedEntry[];
}) {
  const [subs, setSubs] = useState(initialSubscriptions);
  const [entries, setEntries] = useState(initialEntries);
  const [selectedSubId, setSelectedSubId] = useState<string | null>(null);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [addOpen, setAddOpen] = useState(false);

  const refreshSubs = useCallback(async () => {
    setSubs((await getSubscriptions()).items);
  }, []);

  const refreshEntries = useCallback(
    async (subId: string | null = selectedSubId, unread: boolean = unreadOnly) => {
      const out = await getFeedEntries({
        subscriptionId: subId ?? undefined,
        unreadOnly: unread,
      });
      setEntries(out.items);
    },
    [selectedSubId, unreadOnly],
  );

  const selectSub = useCallback(
    async (subId: string | null) => {
      setSelectedSubId(subId);
      setSelectedEntryId(null);
      await refreshEntries(subId);
    },
    [refreshEntries],
  );

  const selectEntry = useCallback(
    (entryId: string) => {
      setSelectedEntryId(entryId);
      const entry = entries.find((e) => e.id === entryId);
      if (entry && !entry.read) {
        // reader convention: opening marks read (unread toggle undoes it)
        setEntries((es) => es.map((e) => (e.id === entryId ? { ...e, read: true } : e)));
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
      if (!window.confirm(`Unsubscribe from "${sub.title}"? Its entries are removed.`)) return;
      await deleteSubscription(sub.id);
      if (selectedSubId === sub.id) {
        setSelectedSubId(null);
        setSelectedEntryId(null);
      }
      await Promise.all([refreshSubs(), refreshEntries(null)]);
    },
    [refreshEntries, refreshSubs, selectedSubId],
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
    await Promise.all([refreshSubs(), refreshEntries()]);
  }, [refreshEntries, refreshSubs, selectedSubId]);

  const toggleUnreadOnly = useCallback(async () => {
    const next = !unreadOnly;
    setUnreadOnly(next);
    await refreshEntries(selectedSubId, next);
  }, [refreshEntries, selectedSubId, unreadOnly]);

  const onGulp = useCallback(async (entry: FeedEntry) => {
    const { snapshot_id } = await gulpEntry(entry.id);
    setEntries((es) =>
      es.map((e) =>
        e.id === entry.id ? { ...e, promoted_source_id: snapshot_id, read: true } : e,
      ),
    );
  }, []);

  const onToggleRead = useCallback(async (entry: FeedEntry) => {
    const next = !entry.read;
    setEntries((es) => es.map((e) => (e.id === entry.id ? { ...e, read: next } : e)));
    setSubs((ss) =>
      ss.map((s) =>
        s.id === entry.subscription_id
          ? { ...s, unread_count: Math.max(0, s.unread_count + (next ? -1 : 1)) }
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
      />
      <EntryReader entry={selectedEntry} onGulp={onGulp} onToggleRead={onToggleRead} />
      <AddFeedDialog open={addOpen} onClose={() => setAddOpen(false)} onSubmit={onAdd} />
    </div>
  );
}
