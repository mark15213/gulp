import Link from "next/link";
import type { Snapshot } from "@gulp/api-client";
import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import { StartButton } from "@/components/snapshot/StartButton";
import { ExportActions } from "@/components/snapshot/ExportActions";
import { safeHost, statusLabel } from "@/lib/pack";
import styles from "./InboxRow.module.css";

export function InboxRow({ item }: { item: Snapshot }) {
  const source = safeHost(item.origin_url);
  const startable = item.status === "unprocessed" || item.status === "needs_attention";
  const exportable = startable || item.status === "exported";
  return (
    <li className={styles.row}>
      <ObjectGlyph type="snapshot" />
      <div className={styles.text}>
        <Link href={`/snapshots/${item.id}`} className={styles.title}>{item.title}</Link>
        <span className={`t-data ${styles.meta}`}>{source}</span>
      </div>
      {startable ? (
        <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
          <StartButton id={item.id} label="▶ Start" />
          <ExportActions id={item.id} status={item.status} />
        </span>
      ) : exportable ? (
        <ExportActions id={item.id} status={item.status} />
      ) : (
        <span className={styles.status}>{statusLabel(item.status)}</span>
      )}
    </li>
  );
}
