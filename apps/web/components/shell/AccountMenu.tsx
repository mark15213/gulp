"use client";

import React from "react";
import { useAuth } from "@/lib/auth";
import styles from "./AccountMenu.module.css";

export function AccountMenu() {
  const { user, signOut } = useAuth();
  const name = user?.display_name || user?.email || "Account";
  const initial = (name[0] ?? "?").toUpperCase();

  return (
    <div className={styles.account}>
      <span className={styles.avatar} aria-hidden="true">
        {initial}
      </span>
      <div className={styles.accountText}>
        <span className={styles.accountName}>{name}</span>
        <span className={styles.accountMeta}>{user?.email}</span>
      </div>
      <button className={styles.logout} onClick={() => void signOut()}>
        Log out
      </button>
    </div>
  );
}
