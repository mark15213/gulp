import { getFeedEntries, getInbox, getSubscriptions } from "@/lib/serverApi";
import { InboxWorkspace } from "@/components/inbox/InboxWorkspace";
import { PageFrame, PageHeader } from "@/components/shell/PageFrame";
import styles from "./page.module.css";

export const dynamic = "force-dynamic"; // always reflect the latest intake

// Inbox — the whole intake surface (spec 2026-08-01): sources · stage sections
// · decision preview. Feeds folded in here; `New` is its first section.
export default async function InboxPage() {
  const [subs, entries, inbox] = await Promise.all([
    getSubscriptions(),
    getFeedEntries(),
    getInbox(),
  ]);
  return (
    <PageFrame variant="workspace" className={styles.page}>
      <PageHeader
        title="Inbox"
        description="Keep or skip, then decide what’s worth digesting."
        meta={<span className="t-data">{inbox.actionable_count} waiting on you</span>}
      />
      <InboxWorkspace
        initialSubscriptions={subs.items}
        initialEntries={entries.items}
        initialEntryCount={entries.count}
        initialItems={inbox.items}
        initialActionable={inbox.actionable_count}
      />
    </PageFrame>
  );
}
