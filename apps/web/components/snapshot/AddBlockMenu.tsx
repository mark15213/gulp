"use client";

import React, { useState } from "react";
import type { BlockType } from "@/lib/packEdit";
import styles from "./Editing.module.css";

const TYPES: BlockType[] = ["prose", "formula", "table", "figure", "list"];

export function AddBlockMenu({ onInsert }: { onInsert: (type: BlockType) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`${styles.addBar} ${open ? styles.open : ""}`}>
      <button
        type="button"
        className={styles.addTrigger}
        aria-label="Add block"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        +
      </button>
      {open && (
        <div className={styles.addMenu}>
          {TYPES.map((t) => (
            <button
              key={t}
              type="button"
              className={styles.iconBtn}
              aria-label={`Add ${t} block`}
              onClick={() => {
                setOpen(false);
                onInsert(t);
              }}
            >
              {t}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
