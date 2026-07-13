import { getFeedEntries, getSubscriptions } from "@/lib/serverApi";
import { FeedsWorkspace } from "@/components/feeds/FeedsWorkspace";
import { PageFrame, PageHeader } from "@/components/shell/PageFrame";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

// Feeds — the stream: follow, browse, and explicitly gulp what's worth it
// (spec 2026-07-09 §5; docs/03 §7.11).
export default async function FeedsPage() {
  const [subs, entries] = await Promise.all([
    getSubscriptions(),
    getFeedEntries(),
  ]);
  return (
    <PageFrame variant="workspace" className={styles.page}>
      <PageHeader
        title="Feeds"
        description="Follow, browse, and forward what’s worth keeping."
      />
      <FeedsWorkspace
        initialSubscriptions={subs.items}
        initialEntries={entries.items}
        initialEntryCount={entries.count}
      />
    </PageFrame>
  );
}
