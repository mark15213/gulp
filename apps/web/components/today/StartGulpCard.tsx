import { Button } from "@/components/ui/Button";
import { IconArrowRight, IconChevronRight } from "@/components/ui/icons";
import type { TodayData } from "@/lib/mock";
import styles from "./StartGulpCard.module.css";

// The "what to do now" hero (docs/03 §7.9): the N due badge + the one primary
// action on the screen. Web register — a tidy stat block, no celebration.
export function StartGulpCard({ data }: { data: TodayData }) {
  return (
    <section className={styles.hero}>
      <div className={styles.body}>
        <p className="t-label">Due now</p>
        <p className={styles.count}>
          <span className={styles.num}>{data.dueCount}</span>
          <span className={styles.unit}>cards due</span>
        </p>
        <p className={styles.meta}>
          across <span className="t-data">{data.dueConcepts}</span> concepts
          <span className={styles.sep}>·</span>
          <span className="t-data">{data.streak}-day</span> streak
        </p>
      </div>

      <div className={styles.action}>
        <Button variant="primary" size="lg" iconRight={<IconArrowRight />}>
          Start Gulp
        </Button>
      </div>

      <a href="#" className={styles.resume}>
        <span>
          Continue where you left off — {data.resume.detail}{" "}
          <span className="t-data">{data.resume.progress}</span>
        </span>
        <IconChevronRight className={styles.resumeChevron} />
      </a>
    </section>
  );
}
