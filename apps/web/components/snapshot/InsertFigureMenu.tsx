"use client";

import React, { useState } from "react";
import { figureUrl, type FigureAssetOut } from "@gulp/api-client";
import styles from "./Editing.module.css";

/** Toolbar affordance: pick an extracted paper figure to insert as a new,
 *  already-linked figure block below the current block. */
export function InsertFigureMenu({
  snapshotId,
  figures,
  onPick,
}: {
  snapshotId: string;
  figures: FigureAssetOut[];
  onPick: (figure: FigureAssetOut) => void;
}) {
  const [open, setOpen] = useState(false);
  if (figures.length === 0) return null;
  return (
    <span className={styles.toolbar}>
      <button
        type="button"
        className={styles.iconBtn}
        aria-label="Insert figure below"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        🖼
      </button>
      {open && (
        <span className={styles.figureGallery}>
          {figures.map((f) => (
            <button
              type="button"
              key={f.id}
              aria-label={f.label ?? "figure"}
              onClick={() => {
                setOpen(false);
                onPick(f);
              }}
            >
              <img src={figureUrl(snapshotId, f.id)} alt={f.label ?? ""} />
            </button>
          ))}
        </span>
      )}
    </span>
  );
}
