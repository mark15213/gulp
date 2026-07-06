"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { deleteSnapshot } from "@gulp/api-client";
import { IconClose, IconTrash } from "@/components/ui/icons";
import styles from "./DeleteSnapshotButton.module.css";

/** Delete a snapshot. Icon-only; `confirm` arms it (a second click) for the library. */
export function DeleteSnapshotButton({ id, confirm = false }: { id: string; confirm?: boolean }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [armed, setArmed] = useState(false);
  const [error, setError] = useState(false);

  async function doDelete() {
    setPending(true);
    setError(false);
    try {
      await deleteSnapshot(id);
      router.refresh();
    } catch {
      setError(true);
      setPending(false);
      setArmed(false);
    }
  }

  function onTrashClick() {
    if (confirm && !armed) {
      setArmed(true); // first click just arms — a second click fires.
      return;
    }
    void doDelete();
  }

  return (
    <span className={styles.group}>
      <button
        type="button"
        className={`${styles.iconBtn} ${armed ? styles.armed : ""}`}
        onClick={onTrashClick}
        disabled={pending}
        aria-label={armed ? "Confirm delete" : "Delete"}
        title={armed ? "Click again to delete" : "Delete"}
      >
        <IconTrash />
      </button>
      {armed && (
        <button
          type="button"
          className={styles.iconBtn}
          onClick={() => setArmed(false)}
          disabled={pending}
          aria-label="Cancel"
          title="Cancel"
        >
          <IconClose />
        </button>
      )}
      {error && (
        <span className={`t-data ${styles.error}`} role="alert">
          Couldn’t delete
        </span>
      )}
    </span>
  );
}
