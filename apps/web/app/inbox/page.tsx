import { getInbox } from "@gulp/api-client";
import { InboxList } from "@/components/inbox/InboxList";
import { PageFrame, PageHeader } from "@/components/shell/PageFrame";
import styles from "./page.module.css";

export const dynamic = "force-dynamic"; // always reflect the latest captures

export default async function InboxPage() {
  const inbox = await getInbox();
  return (
    <PageFrame className={styles.page}>
      <PageHeader
        title="Inbox"
        description={<span className="t-data">{inbox.count} awaiting</span>}
      />
      <InboxList items={inbox.items} />
    </PageFrame>
  );
}
