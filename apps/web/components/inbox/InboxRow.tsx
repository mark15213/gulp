import Link from "next/link";
import type { Snapshot } from "@gulp/api-client";
import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import { StartButton } from "@/components/snapshot/StartButton";
import { safeHost } from "@/lib/pack";
import styles from "./InboxRow.module.css";

function statusLabel(status: Snapshot["status"]): string {
  if (status === "processing" || status === "queued") return "Processing";
  if (status === "needs_attention") return "Needs attention";
  if (status === "unprocessed") return "Not started";
  return "Ready";
}

export function InboxRow({ item }: { item: Snapshot }) {
  const source = safeHost(item.origin_url);
  const startable = item.status === "unprocessed" || item.status === "needs_attention";
  return (
    <li className={styles.row}>
      <ObjectGlyph type="snapshot" />
      <div className={styles.text}>
        <Link href={`/snapshots/${item.id}`} className={styles.title}>{item.title}</Link>
        <span className={`t-data ${styles.meta}`}>{source}</span>
      </div>
      {startable ? (
        <StartButton id={item.id} label="▶ Start" />
      ) : (
        <span className={styles.status}>{statusLabel(item.status)}</span>
      )}
    </li>
  );
}
