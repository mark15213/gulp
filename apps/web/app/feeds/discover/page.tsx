import Link from "next/link";
import { DiscoverSearch } from "@/components/feeds/DiscoverSearch";
import styles from "./page.module.css";

// Discover — browse the RSSHub route catalog (1,675 namespaces) and a curated
// starter list; paste any address to subscribe (spec 2026-07-09 §5).
export default function DiscoverPage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className="t-title-l">Discover</h1>
        <Link href="/feeds" className={styles.back}>
          ← Feeds
        </Link>
      </header>
      <DiscoverSearch />
    </div>
  );
}
