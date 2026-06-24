import { Button } from "@/components/ui/Button";
import { IconCheck } from "@/components/ui/icons";
import styles from "./ConfirmCard.module.css";

// The "N new to confirm" batch-review card (docs/03 §7.9): the lightweight
// review path. Approve-all stays secondary — the screen's one primary is Start
// Gulp (blue is rationed, §1.2.2).
export function ConfirmCard({ count }: { count: number }) {
  return (
    <section className={styles.card}>
      <div className={styles.text}>
        <p className={styles.headline}>
          <span className="t-data">{count}</span> new packs to confirm
        </p>
        <p className={styles.sub}>
          AI drafted cards from what you captured. Approve all, or review each.
        </p>
      </div>
      <div className={styles.actions}>
        <Button variant="ghost">Review</Button>
        <Button variant="secondary" iconLeft={<IconCheck />}>
          Approve all
        </Button>
      </div>
    </section>
  );
}
