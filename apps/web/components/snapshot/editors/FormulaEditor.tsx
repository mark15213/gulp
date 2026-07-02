"use client";

import React, { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { Md } from "../Md";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function FormulaEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "formula" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [latex, setLatex] = useState(block.latex);
  const [explanation, setExplanation] = useState(block.explanation);
  return (
    <EditorShell
      onSave={() => onSave({ type: "formula", latex, explanation })}
      onCancel={onCancel}
    >
      <div className={styles.field}>
        <label htmlFor="formula-latex">LaTeX</label>
        <textarea
          id="formula-latex"
          aria-label="LaTeX"
          className={styles.textarea}
          value={latex}
          onChange={(e) => setLatex(e.target.value)}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor="formula-exp">Explanation</label>
        <input
          id="formula-exp"
          aria-label="Explanation"
          className={styles.input}
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
        />
      </div>
      <div className={styles.preview}>
        <Md>{`$$\n${latex}\n$$`}</Md>
      </div>
    </EditorShell>
  );
}
