import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import { StateChip } from "@/components/ui/StateChip";
import type { DigestItem } from "@/lib/mock";
import styles from "./DigestCard.module.css";

// Object card (docs/03 §7.1): type glyph · title · summary · mono meta · state
// chip. Digest variant adds the per-item "why it connects" reason (§7.11).
export function DigestCard({ item }: { item: DigestItem }) {
  return (
    <article className={styles.card}>
      <div className={styles.top}>
        <ObjectGlyph type={item.type} />
        <StateChip
          state={item.state}
          count={item.state === "due" ? item.cards : undefined}
        />
      </div>

      <h3 className={`t-title-s ${styles.title}`}>{item.title}</h3>
      <p className={`t-body-s ${styles.summary}`}>{item.summary}</p>

      <p className={styles.reason}>{item.reason}</p>

      <div className={styles.meta}>
        <span className="t-data">{item.source}</span>
        <span className={styles.dot}>·</span>
        <span className="t-data">{item.time}</span>
        <span className={styles.cards}>
          <span className="t-data">+{item.cards}</span> cards
        </span>
      </div>
    </article>
  );
}
