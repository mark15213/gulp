import type { Snapshot } from "@gulp/api-client";
import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import styles from "./InboxRow.module.css";

function statusLabel(status: Snapshot["status"]): string {
  if (status === "processing" || status === "queued") return "Processing";
  if (status === "needs_attention") return "Needs attention";
  return "Ready";
}

export function InboxRow({ item }: { item: Snapshot }) {
  const source = item.origin_url ? new URL(item.origin_url).host : "Note";
  return (
    <li className={styles.row}>
      <ObjectGlyph type="snapshot" />
      <div className={styles.text}>
        <span className={styles.title}>{item.title}</span>
        <span className={`t-data ${styles.meta}`}>{source}</span>
      </div>
      {item.origin_url && (
        <a className={styles.open} href={item.origin_url} target="_blank" rel="noreferrer">
          Open original
        </a>
      )}
      <span className={styles.status}>{statusLabel(item.status)}</span>
    </li>
  );
}
