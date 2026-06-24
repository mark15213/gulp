import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import { IconAlert } from "@/components/ui/icons";
import type { RecentItem } from "@/lib/mock";
import styles from "./CapturePeek.module.css";

// Read-only "recently captured / processing" peek (docs/03 §7.9), exercising
// the Processing skeleton and Needs-attention states (§8).
export function CapturePeek({ items }: { items: RecentItem[] }) {
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <li
          key={item.id}
          className={`${styles.row} ${item.status === "attention" ? styles.attentionRow : ""}`}
        >
          <ObjectGlyph type={item.type} />
          <div className={styles.text}>
            <span className={styles.title}>{item.title}</span>
            <span className={styles.meta}>
              <span className="t-data">{item.source}</span>
              <span className={styles.dot}>·</span>
              <span className="t-data">{item.time}</span>
            </span>
          </div>
          <StatusTag status={item.status} />
        </li>
      ))}
    </ul>
  );
}

function StatusTag({ status }: { status: RecentItem["status"] }) {
  if (status === "processing") {
    return (
      <span className={styles.processing}>
        <span className={styles.shimmer} aria-hidden="true" />
        <span className="t-label">processing</span>
      </span>
    );
  }
  if (status === "attention") {
    return (
      <span className={styles.attention}>
        <IconAlert className={styles.attentionIcon} />
        Needs attention
      </span>
    );
  }
  return <span className={styles.ready}>Ready</span>;
}
