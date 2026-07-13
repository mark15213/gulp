import React from "react";
import Link from "next/link";
import styles from "./SettingsHome.module.css";

// Entry page for the Settings destination (spec 2026-07-13 settings entry).
// One card per section; unimplemented sections are inert placeholders.
const SECTIONS = [
  {
    key: "ai",
    title: "AI models",
    description: "Bring your own provider keys and pick the default model.",
    href: "/settings/ai",
  },
  {
    key: "account",
    title: "Account",
    description: "Display name, email, and password.",
  },
  {
    key: "preferences",
    title: "Preferences",
    description: "Language and appearance.",
  },
  {
    key: "notifications",
    title: "Notifications",
    description: "Quiet mode and per-type toggles.",
  },
] as const;

export function SettingsHome() {
  return (
    <div className={styles.root}>
      <h1 className={styles.title}>Settings</h1>
      {SECTIONS.map((s) =>
        "href" in s ? (
          <Link key={s.key} href={s.href} className={styles.card}>
            <span className={styles.cardTitle}>{s.title}</span>
            <span className={styles.cardDescription}>{s.description}</span>
          </Link>
        ) : (
          <div
            key={s.key}
            className={`${styles.card} ${styles.cardDisabled}`}
            aria-disabled="true"
          >
            <span className={styles.cardTitle}>
              {s.title}
              <span className={styles.chip}>Coming soon</span>
            </span>
            <span className={styles.cardDescription}>{s.description}</span>
          </div>
        ),
      )}
    </div>
  );
}
