import React from "react";
import { IconSettings } from "@/components/ui/icons";
import { getInbox } from "@gulp/api-client";
import { SidebarNav } from "./SidebarNav";
import { SearchCommand } from "./SearchCommand";
import styles from "./Sidebar.module.css";

export async function Sidebar() {
  const { count } = await getInbox();
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <span className={styles.mark} aria-hidden="true" />
        <span className={styles.wordmark}>Gulp</span>
      </div>

      <SearchCommand />

      <SidebarNav inboxCount={count} />

      <div className={styles.foot}>
        <span
          className={`${styles.item} ${styles.itemDisabled}`}
          aria-disabled="true"
          title="Coming soon"
        >
          <IconSettings className={styles.itemIcon} />
          <span className={styles.itemLabel}>Settings</span>
        </span>
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
