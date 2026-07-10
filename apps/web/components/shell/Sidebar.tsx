import React from "react";
import Image from "next/image";
import { IconSettings } from "@/components/ui/icons";
import { getInbox } from "@gulp/api-client";
import { SidebarNav } from "./SidebarNav";
import { SearchCommand } from "./SearchCommand";
import { AccountMenu } from "./AccountMenu";
import styles from "./Sidebar.module.css";

export async function Sidebar() {
  const { count } = await getInbox();
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <Image
          src="/gulp-mark.png"
          alt="Gulp"
          width={26}
          height={26}
          className={styles.mark}
          priority
        />
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
        <AccountMenu />
      </div>
    </aside>
  );
}
