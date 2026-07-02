"use client";

import React, { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function ListEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "list" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState(block.items.join("\n"));
  const [ordered, setOrdered] = useState(block.ordered);
  function save() {
    const items = text
      .split("\n")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    onSave({ type: "list", items, ordered });
  }
  return (
    <EditorShell onSave={save} onCancel={onCancel}>
      <div className={styles.field}>
        <label htmlFor="list-items">List items (one per line)</label>
        <textarea
          id="list-items"
          aria-label="List items (one per line)"
          className={styles.textarea}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      <label>
        <input
          type="checkbox"
          aria-label="Ordered list"
          checked={ordered}
          onChange={(e) => setOrdered(e.target.checked)}
        />{" "}
        Ordered
      </label>
    </EditorShell>
  );
}
