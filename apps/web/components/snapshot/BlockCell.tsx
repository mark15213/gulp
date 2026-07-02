import React from "react";
import styles from "./BlockCell.module.css";

// Per-block wrapper. Phase 1 only carries the stable id; Phases 2–3 add the
// hover toolbar, edit mode, and chat trigger onto this same cell.
export function BlockCell({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <div className={styles.cell} data-block-id={id}>
      {children}
    </div>
  );
}
