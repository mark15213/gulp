import type { Snapshot } from "@gulp/api-client";
import { InboxRow } from "./InboxRow";
import styles from "./InboxRow.module.css";

export function InboxList({ items }: { items: Snapshot[] }) {
  if (items.length === 0) {
    return (
      <p className={styles.empty}>
        Nothing here yet — capture your first thing with ⌘K.
      </p>
    );
  }
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <InboxRow key={item.id} item={item} />
      ))}
    </ul>
  );
}
