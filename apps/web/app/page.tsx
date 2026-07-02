export const dynamic = "force-dynamic";

import { StartGulpCard } from "@/components/today/StartGulpCard";
import { DigestCard } from "@/components/today/DigestCard";
import { CapturePeek } from "@/components/today/CapturePeek";
import { today } from "@/lib/mock";
import { getInbox } from "@gulp/api-client";
import styles from "./page.module.css";

// Today — the web "what should I do right now?" landing (docs/03 §7.9).
export default async function TodayPage() {
  const inbox = await getInbox();
  const recent = inbox.items.slice(0, 3).map((s) => ({
    id: s.id,
    type: "snapshot" as const,
    title: s.title,
    source: s.origin_url ? new URL(s.origin_url).host : "Note",
    time: "just now",
    status: (s.status === "needs_attention"
      ? "attention"
      : s.status === "ready"
        ? "ready"
        : "processing") as "ready" | "processing" | "attention",
  }));
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

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className="t-label">Recently captured</p>
          <a href="/inbox" className={styles.seeAll}>
            Open Inbox
          </a>
        </div>
        <CapturePeek items={recent} />
      </section>
    </div>
  );
}
