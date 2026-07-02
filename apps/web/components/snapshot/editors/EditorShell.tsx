import React from "react";
import { Button } from "@/components/ui/Button";
import styles from "../Editing.module.css";

export function EditorShell({
  onSave,
  onCancel,
  children,
}: {
  onSave: () => void;
  onCancel: () => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      {children}
      <div className={styles.actions}>
        <Button variant="primary" onClick={onSave}>
          Save
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
