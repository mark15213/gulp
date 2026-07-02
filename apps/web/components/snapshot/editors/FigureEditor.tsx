"use client";

import React, { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function FigureEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "figure" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [label, setLabel] = useState(block.label);
  const [explanation, setExplanation] = useState(block.explanation);
  return (
    <EditorShell onSave={() => onSave({ type: "figure", label, explanation })} onCancel={onCancel}>
      <div className={styles.field}>
        <label htmlFor="figure-label">Label</label>
        <input
          id="figure-label"
          aria-label="Label"
          className={styles.input}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor="figure-exp">Explanation</label>
        <textarea
          id="figure-exp"
          className={styles.textarea}
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
        />
      </div>
    </EditorShell>
  );
}
