import { getFeedEntries, getSubscriptions } from "@gulp/api-client";
import { FeedsWorkspace } from "@/components/feeds/FeedsWorkspace";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

// Feeds — the stream: follow, browse, and explicitly gulp what's worth it
// (spec 2026-07-09 §5; docs/03 §7.11).
export default async function FeedsPage() {
  const [subs, entries] = await Promise.all([getSubscriptions(), getFeedEntries()]);
  return (
    <div className={styles.page}>
      <FeedsWorkspace initialSubscriptions={subs.items} initialEntries={entries.items} />
    </div>
  );
}
