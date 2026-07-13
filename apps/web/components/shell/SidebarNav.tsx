"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getInbox } from "@gulp/api-client";
import {
  IconToday,
  IconInbox,
  IconLibrary,
  IconFeeds,
} from "@/components/ui/icons";
import styles from "./Sidebar.module.css";

// Single-gate nav (spec 2026-07-02): Today first, then the conveyor belt
// (Inbox = to-do), the shelf (Library = ready), and the stream (Feeds —
// spec 2026-07-09). Knowledge bases are parked (tags cover grouping).
const NAV = [
  { label: "Today", href: "/", icon: IconToday },
  { label: "Feeds", href: "/feeds", icon: IconFeeds },
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
  const [latest, setLatest] = useState<{
    pathname: string;
    seed: number;
    count: number;
  } | null>(null);

  // Root layouts persist across App Router navigations, so Sidebar's server
  // count can outlive the Inbox page that produced it. Keep that SSR value for
  // the first paint, then reconcile whenever this nav mounts, the route
  // changes, or router.refresh() supplies a new server count.
  useEffect(() => {
    let active = true;
    getInbox()
      .then(({ count }) => {
        if (active) setLatest({ pathname, seed: inboxCount, count });
      })
      .catch(() => {
        // A failed background refresh should not hide a valid server count.
      });
    return () => {
      active = false;
    };
  }, [pathname, inboxCount]);

  const displayedInboxCount =
    latest?.pathname === pathname && latest.seed === inboxCount
      ? latest.count
      : inboxCount;

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
            {label === "Inbox" && displayedInboxCount > 0 && (
              <span className={styles.itemCount}>{displayedInboxCount}</span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
