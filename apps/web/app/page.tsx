import { StartGulpCard } from "@/components/today/StartGulpCard";
import { DigestCard } from "@/components/today/DigestCard";
import { ConfirmCard } from "@/components/today/ConfirmCard";
import { CapturePeek } from "@/components/today/CapturePeek";
import { today } from "@/lib/mock";
import styles from "./page.module.css";

// Today — the web "what should I do right now?" landing (docs/03 §7.9).
export default function TodayPage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className="t-title-l">Today</h1>
          <p className={styles.greeting}>{today.greeting}</p>
        </div>
        <span className={`t-data ${styles.dateChip}`}>{today.date}</span>
      </header>

      <StartGulpCard data={today} />

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className="t-label">Daily digest</p>
          <a href="#" className={styles.seeAll}>
            See all
          </a>
        </div>
        <div className={styles.digestGrid}>
          {today.digest.map((item) => (
            <DigestCard key={item.id} item={item} />
          ))}
        </div>
      </section>

      <ConfirmCard count={today.newToConfirm} />

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className="t-label">Recently captured</p>
          <a href="#" className={styles.seeAll}>
            Open Inbox
          </a>
        </div>
        <CapturePeek items={today.recent} />
      </section>
    </div>
  );
}
