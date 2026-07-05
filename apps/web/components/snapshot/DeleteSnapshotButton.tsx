"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { deleteSnapshot } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";

/** Delete a snapshot (inbox or library). `confirm` gates it behind a two-step inline prompt. */
export function DeleteSnapshotButton({ id, confirm = false }: { id: string; confirm?: boolean }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [confirming, setConfirming] = useState(false);
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
      setConfirming(false);
    }
  }

  const wrap = { display: "inline-flex", gap: 8, alignItems: "center" } as const;

  if (confirming) {
    return (
      <span style={wrap}>
        <span className="t-data">Delete?</span>
        <Button variant="danger" onClick={doDelete} disabled={pending}>
          {pending ? "Deleting…" : "Yes"}
        </Button>
        <Button variant="ghost" onClick={() => setConfirming(false)} disabled={pending}>
          Cancel
        </Button>
      </span>
    );
  }

  return (
    <span style={wrap}>
      <Button
        variant="danger"
        onClick={confirm ? () => setConfirming(true) : doDelete}
        disabled={pending}
        aria-label="Delete"
      >
        {pending ? "Deleting…" : "Delete"}
      </Button>
      {error && (
        <span className="t-data" role="alert" style={{ color: "var(--danger, #c00)" }}>
          Couldn’t delete — try again.
        </span>
      )}
    </span>
  );
}
