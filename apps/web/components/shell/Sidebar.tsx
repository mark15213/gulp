import React from "react";
import Image from "next/image";
import { getInbox } from "@gulp/api-client";
import { SidebarNav } from "./SidebarNav";
import { SearchCommand } from "./SearchCommand";
import { AccountMenu } from "./AccountMenu";
import { SettingsLink } from "./SettingsLink";
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
        <SettingsLink />
        <AccountMenu />
      </div>
    </aside>
  );
}
