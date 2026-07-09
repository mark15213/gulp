"use client";

import React, { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function CodeEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "code" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [language, setLanguage] = useState(block.language ?? "");
  const [content, setContent] = useState(block.content);
  return (
    <EditorShell
      onSave={() => onSave({ type: "code", language: language.trim() || null, content })}
      onCancel={onCancel}
    >
      <div className={styles.field}>
        <label htmlFor="code-lang">Language</label>
        <input
          id="code-lang"
          aria-label="Language"
          className={styles.input}
          value={language}
          placeholder="python"
          onChange={(e) => setLanguage(e.target.value)}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor="code-src">Code</label>
        <textarea
          id="code-src"
          aria-label="Code"
          className={styles.textarea}
          value={content}
          spellCheck={false}
          onChange={(e) => setContent(e.target.value)}
        />
      </div>
    </EditorShell>
  );
}
