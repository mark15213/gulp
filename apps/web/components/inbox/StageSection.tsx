"use client";

import React from "react";
import styles from "./InboxWorkspace.module.css";

/** A collapsible stage group. Collapsing `New` turns the surface into a pure
 *  work queue — the "process only, don't scan today" visit (spec §4.2). */
export function StageSection({
  label,
  question,
  count,
  collapsed,
  onToggle,
  empty,
  controls,
  footer,
  children,
}: {
  label: string;
  question: string;
  count: number;
  collapsed: boolean;
  onToggle: () => void;
  empty: string;
  controls?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode[];
}) {
  return (
    <section className={`${styles.section} ${collapsed ? styles.collapsed : ""}`}>
      <div className={styles.sectionHead}>
        <button
          type="button"
          className={styles.sectionToggle}
          aria-expanded={!collapsed}
          onClick={onToggle}
        >
          <svg className={styles.caret} viewBox="0 0 10 10" aria-hidden="true">
            <path d="M1 3l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" />
          </svg>
          <span className="t-label">{label}</span>
          <span className={`t-data ${styles.sectionCount}`}>{count}</span>
          <span className={styles.sectionQuestion}>{question}</span>
        </button>
        {controls}
      </div>
      {!collapsed &&
        (children.length > 0 ? (
          <ul className={styles.rows}>{children}</ul>
        ) : (
          <p className={styles.sectionEmpty}>{empty}</p>
        ))}
      {!collapsed && footer}
    </section>
  );
}
