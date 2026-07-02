"use client";

import React, { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { Md } from "../Md";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function ProseEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "prose" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [content, setContent] = useState(block.content);
  return (
    <EditorShell onSave={() => onSave({ type: "prose", content })} onCancel={onCancel}>
      <div className={styles.field}>
        <label htmlFor="prose-src">Prose (Markdown)</label>
        <textarea
          id="prose-src"
          aria-label="Prose (Markdown)"
          className={styles.textarea}
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
      </div>
      <div className={styles.preview}>
        <Md>{content}</Md>
      </div>
    </EditorShell>
  );
}
