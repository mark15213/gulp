import type { Snapshot } from "@gulp/api-client";
import { InboxRow } from "./InboxRow";

export function InboxList({ items }: { items: Snapshot[] }) {
  if (items.length === 0) {
    return (
      <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>
        Nothing here yet — capture your first thing with ⌘K.
      </p>
    );
  }
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {items.map((item) => (
        <InboxRow key={item.id} item={item} />
      ))}
    </ul>
  );
}
