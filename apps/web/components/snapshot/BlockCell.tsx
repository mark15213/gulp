"use client";

import React, { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { BlockView } from "./BlockView";
import { BlockEditor } from "./editors/BlockEditor";
import { BlockToolbar } from "./BlockToolbar";
import styles from "./BlockCell.module.css";

export function BlockCell({
  block,
  canMoveUp,
  canMoveDown,
  onSaveContent,
  onDelete,
  onMoveUp,
  onMoveDown,
}: {
  block: PackBlockOut;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onSaveContent: (content: BlockWrite) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const [editing, setEditing] = useState(false);
  return (
    <div className={styles.cell} data-block-id={block.id}>
      {editing ? (
        <BlockEditor
          block={block}
          onSave={(content) => {
            setEditing(false);
            onSaveContent(content);
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <>
          <div className={styles.toolbarSlot}>
            <BlockToolbar
              onEdit={() => setEditing(true)}
              onDelete={onDelete}
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              canMoveUp={canMoveUp}
              canMoveDown={canMoveDown}
            />
          </div>
          <BlockView block={block} />
        </>
      )}
    </div>
  );
}
