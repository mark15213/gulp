import type { ComponentType, SVGProps } from "react";
import {
  IconToday,
  IconInbox,
  IconLibrary,
  IconFeeds,
  IconKnowledge,
  IconSearch,
  IconSettings,
} from "@/components/ui/icons";
import styles from "./Sidebar.module.css";

type NavItem = {
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  active?: boolean;
  count?: number;
};

// docs/03 §5.2 — Today · Inbox · Library · Feeds · Knowledge bases. Search is
// not a nav row: the ⌘K field below the wordmark is the single search entry
// point (it doubles as the command bar). Only Today is wired in this static
// slice; the rest are inert placeholders.
const NAV: NavItem[] = [
  { label: "Today", icon: IconToday, active: true },
  { label: "Inbox", icon: IconInbox, count: 3 },
  { label: "Library", icon: IconLibrary },
  { label: "Feeds", icon: IconFeeds },
  { label: "Knowledge bases", icon: IconKnowledge },
];

export function Sidebar() {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <span className={styles.mark} aria-hidden="true" />
        <span className={styles.wordmark}>Gulp</span>
      </div>

      <button type="button" className={styles.search}>
        <IconSearch className={styles.searchIcon} />
        <span>Search</span>
        <kbd className={styles.kbd}>⌘K</kbd>
      </button>

      <nav className={styles.nav} aria-label="Primary">
        {NAV.map(({ label, icon: Glyph, active, count }) => (
          <a
            key={label}
            href="#"
            className={`${styles.item} ${active ? styles.active : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <Glyph className={styles.itemIcon} />
            <span className={styles.itemLabel}>{label}</span>
            {count !== undefined && (
              <span className={styles.itemCount}>{count}</span>
            )}
          </a>
        ))}
      </nav>

      <div className={styles.foot}>
        <a href="#" className={styles.item}>
          <IconSettings className={styles.itemIcon} />
          <span className={styles.itemLabel}>Settings</span>
        </a>
        <div className={styles.account}>
          <span className={styles.avatar} aria-hidden="true">
            M
          </span>
          <div className={styles.accountText}>
            <span className={styles.accountName}>Mark</span>
            <span className={styles.accountMeta}>Free plan</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
