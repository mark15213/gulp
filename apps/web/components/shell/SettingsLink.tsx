"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconSettings } from "@/components/ui/icons";
import { isActive } from "./SidebarNav";
import styles from "./Sidebar.module.css";

export function SettingsLink() {
  const active = isActive(usePathname(), "/settings");
  return (
    <Link
      href="/settings"
      className={`${styles.item} ${active ? styles.active : ""}`}
      aria-current={active ? "page" : undefined}
    >
      <IconSettings className={styles.itemIcon} />
      <span className={styles.itemLabel}>Settings</span>
    </Link>
  );
}
