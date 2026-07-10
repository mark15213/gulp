"use client";

import React, { useState } from "react";
import type { Snapshot } from "@gulp/api-client";
import { addSnapshotTag, removeSnapshotTag } from "@gulp/api-client";
import styles from "./RowTags.module.css";

export function RowTags({
  snapshotId,
  sourceFeed,
  tags,
  onTagsChange,
  onSourceClick,
}: {
  snapshotId: string;
  sourceFeed: Snapshot["source_feed"];
  tags: string[];
  onTagsChange: (tags: string[]) => void;
  onSourceClick: (title: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [value, setValue] = useState("");

  async function commitAdd() {
    const t = value.trim();
    setAdding(false);
    setValue("");
    if (!t || tags.includes(t)) return;
    const prev = tags;
    onTagsChange([...tags, t]); // optimistic
    try {
      await addSnapshotTag(snapshotId, t);
    } catch {
      onTagsChange(prev); // rollback
    }
  }

  async function removeTag(t: string) {
    const prev = tags;
    onTagsChange(tags.filter((x) => x !== t)); // optimistic
    try {
      await removeSnapshotTag(snapshotId, t);
    } catch {
      onTagsChange(prev); // rollback
    }
  }

  return (
    <span className={styles.tags}>
      {sourceFeed && (
        <button
          type="button"
          className={styles.source}
          onClick={() => onSourceClick(sourceFeed.title)}
          title={`Filter by ${sourceFeed.title}`}
        >
          {sourceFeed.title}
        </button>
      )}
      {tags.map((t) => (
        <span key={t} className={styles.tag}>
          {t}
          <button
            type="button"
            className={styles.remove}
            aria-label={`Remove tag ${t}`}
            onClick={() => removeTag(t)}
          >
            ×
          </button>
        </span>
      ))}
      {adding ? (
        <input
          className={styles.input}
          autoFocus
          value={value}
          placeholder="tag"
          onChange={(e) => setValue(e.target.value)}
          onBlur={commitAdd}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitAdd();
            if (e.key === "Escape") {
              setAdding(false);
              setValue("");
            }
          }}
        />
      ) : (
        <button
          type="button"
          className={styles.add}
          aria-label="Add tag"
          onClick={() => setAdding(true)}
        >
          +
        </button>
      )}
    </span>
  );
}
