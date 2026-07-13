export const dynamic = "force-dynamic";

import React from "react";
import Link from "next/link";
import { StartGulpCard } from "@/components/today/StartGulpCard";
import { MasteryTally } from "@/components/today/MasteryTally";
import { DigestCard } from "@/components/today/DigestCard";
import { CapturePeek, type RecentItem } from "@/components/today/CapturePeek";
import { getCurrentGulpSession, getToday } from "@/lib/serverApi";
import { safeHost } from "@/lib/pack";
import { timeAgo } from "@/lib/time";
import { PageFrame, PageHeader } from "@/components/shell/PageFrame";
import styles from "./page.module.css";

// Today — the web "what should I do right now?" landing (docs/03 §7.9).
export default async function TodayPage() {
  const today = await getToday();
  // A missing/unreachable session shouldn't fail the whole page — it just
  // means the CTA reads "Start" instead of "Resume" (S4 §7).
  const current = await getCurrentGulpSession().catch(() => null);
  const date = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
  const recent: RecentItem[] = today.recent.map((s) => ({
    id: s.id,
    type: "snapshot",
    title: s.title,
    source: safeHost(s.origin_url),
    time: timeAgo(s.created_at),
    status:
      s.status === "needs_attention"
        ? "attention"
        : s.status === "ready"
          ? "ready"
          : "processing",
  }));

  return (
    <PageFrame variant="dashboard" className={styles.page}>
      <PageHeader
        title="Today"
        description={<>Here&apos;s what&apos;s worth your 5 minutes.</>}
        meta={date}
      />

      <div className={styles.overview}>
        <StartGulpCard
          acceptedCards={today.accepted_cards}
          cardSources={today.card_sources}
          dueCount={today.due_count}
          newCount={today.new_count}
          hasResumable={!!current}
        />

        <MasteryTally mastery={today.mastery} />
      </div>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className="t-label">Recently ready</p>
          <Link href="/library" className={styles.seeAll}>
            See all
          </Link>
        </div>
        {today.digest.length > 0 ? (
          <div className={styles.digestGrid}>
            {today.digest.map((item) => (
              <DigestCard key={item.snapshot.id} item={item} />
            ))}
          </div>
        ) : (
          <p className={styles.empty}>
            Nothing ready yet — process a capture from your Inbox.
          </p>
        )}
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className="t-label">Recently captured</p>
          <Link href="/inbox" className={styles.seeAll}>
            Open Inbox
          </Link>
        </div>
        {recent.length > 0 ? (
          <CapturePeek items={recent} />
        ) : (
          <p className={styles.empty}>Inbox is clear.</p>
        )}
      </section>
    </PageFrame>
  );
}
