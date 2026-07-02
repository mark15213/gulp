import React from "react";
import styles from "./Editing.module.css";

export function BlockToolbar({
  onEdit,
  onDelete,
  onMoveUp,
  onMoveDown,
  onDiscuss,
  canMoveUp,
  canMoveDown,
}: {
  onEdit: () => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDiscuss: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
}) {
  return (
    <div className={styles.toolbar}>
      <button type="button" className={styles.iconBtn} aria-label="Edit block" onClick={onEdit}>
        Edit
      </button>
      <button
        type="button"
        className={styles.iconBtn}
        aria-label="Move block up"
        onClick={onMoveUp}
        disabled={!canMoveUp}
      >
        ↑
      </button>
      <button
        type="button"
        className={styles.iconBtn}
        aria-label="Move block down"
        onClick={onMoveDown}
        disabled={!canMoveDown}
      >
        ↓
      </button>
      <button type="button" className={styles.iconBtn} aria-label="Discuss block" onClick={onDiscuss}>
        💬
      </button>
      <button type="button" className={styles.iconBtn} aria-label="Delete block" onClick={onDelete}>
        Delete
      </button>
    </div>
  );
}
