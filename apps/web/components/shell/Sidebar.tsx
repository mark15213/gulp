import React, { type ComponentType, type SVGProps } from "react";
import {
  IconToday,
  IconInbox,
  IconLibrary,
  IconSearch,
  IconSettings,
} from "@/components/ui/icons";
import { getInbox } from "@gulp/api-client";
import styles from "./Sidebar.module.css";

type NavItem = {
  label: string;
  href: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  active?: boolean;
};

// Single-gate nav (spec 2026-07-02): Today first, then the conveyor belt
// (Inbox = to-do) and the shelf (Library = ready). Feeds returns with S7;
// Knowledge bases are parked (tags cover grouping). Search stays the ⌘K field.
const NAV: NavItem[] = [
  { label: "Today", href: "/", icon: IconToday, active: true },
  { label: "Inbox", href: "/inbox", icon: IconInbox },
  { label: "Library", href: "/library", icon: IconLibrary },
];

export async function Sidebar() {
  const { count } = await getInbox();
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
        {NAV.map(({ label, href, icon: Glyph, active }) => (
          <a
            key={label}
            href={href}
            className={`${styles.item} ${active ? styles.active : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <Glyph className={styles.itemIcon} />
            <span className={styles.itemLabel}>{label}</span>
            {label === "Inbox" && count > 0 && (
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
