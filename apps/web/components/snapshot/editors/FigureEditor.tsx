"use client";

import React, { useEffect, useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import { getFigures, figureUrl, type FigureAssetOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function FigureEditor({
  snapshotId,
  block,
  onSave,
  onCancel,
}: {
  snapshotId: string;
  block: Extract<PackBlockOut, { type: "figure" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [label, setLabel] = useState(block.label);
  const [explanation, setExplanation] = useState(block.explanation);
  const [figureId, setFigureId] = useState<string | null>(block.figure_id ?? null);
  const [gallery, setGallery] = useState<FigureAssetOut[]>([]);

  useEffect(() => {
    // Only fetch for a real snapshot id — a malformed id would 422 the API.
    if (!UUID_RE.test(snapshotId)) return;
    let alive = true;
    getFigures(snapshotId)
      .then((figs) => alive && setGallery(figs))
      .catch(() => alive && setGallery([]));
    return () => {
      alive = false;
    };
  }, [snapshotId]);

  return (
    <EditorShell
      onSave={() => onSave({ type: "figure", label, explanation, figure_id: figureId })}
      onCancel={onCancel}
    >
      {gallery.length > 0 && (
        <div className={styles.field}>
          <span>Figures from the paper</span>
          <div className={styles.figureGallery}>
            {gallery.map((f) => (
              <button
                type="button"
                key={f.id}
                aria-label={f.label ?? "figure"}
                aria-pressed={figureId === f.id}
                onClick={() => setFigureId(figureId === f.id ? null : f.id)}
              >
                <img src={figureUrl(snapshotId, f.id)} alt={f.label ?? ""} />
              </button>
            ))}
          </div>
        </div>
      )}
      <div className={styles.field}>
        <label htmlFor="figure-label">Label</label>
        <input id="figure-label" aria-label="Label" className={styles.input}
          value={label} onChange={(e) => setLabel(e.target.value)} />
      </div>
      <div className={styles.field}>
        <label htmlFor="figure-exp">Explanation</label>
        <textarea id="figure-exp" className={styles.textarea}
          value={explanation} onChange={(e) => setExplanation(e.target.value)} />
      </div>
    </EditorShell>
  );
}
