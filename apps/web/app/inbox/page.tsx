import { getInbox } from "@gulp/api-client";
import { InboxList } from "@/components/inbox/InboxList";

export const dynamic = "force-dynamic"; // always reflect the latest captures

export default async function InboxPage() {
  const inbox = await getInbox();
  return (
    <div style={{ padding: "24px" }}>
      <h1 className="t-title-l">Inbox</h1>
      <p className="t-data" style={{ color: "var(--text-muted, #777)", marginBottom: 16 }}>
        {inbox.count} awaiting
      </p>
      <InboxList items={inbox.items} />
    </div>
  );
}
