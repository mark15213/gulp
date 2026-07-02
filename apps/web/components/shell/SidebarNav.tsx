"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconToday, IconInbox, IconLibrary } from "@/components/ui/icons";
import styles from "./Sidebar.module.css";

// Single-gate nav (spec 2026-07-02): Today first, then the conveyor belt
// (Inbox = to-do) and the shelf (Library = ready). Feeds returns with S7;
// Knowledge bases are parked (tags cover grouping).
const NAV = [
  { label: "Today", href: "/", icon: IconToday },
  { label: "Inbox", href: "/inbox", icon: IconInbox },
  { label: "Library", href: "/library", icon: IconLibrary },
] as const;

// Today only on the exact root; sections match themselves and their subtree.
// /snapshots/[id] is reachable from both Inbox and Library, so nothing lights up.
export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SidebarNav({ inboxCount }: { inboxCount: number }) {
  const pathname = usePathname();
  return (
    <nav className={styles.nav} aria-label="Primary">
      {NAV.map(({ label, href, icon: Glyph }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={label}
            href={href}
            className={`${styles.item} ${active ? styles.active : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <Glyph className={styles.itemIcon} />
            <span className={styles.itemLabel}>{label}</span>
            {label === "Inbox" && inboxCount > 0 && (
              <span className={styles.itemCount}>{inboxCount}</span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
