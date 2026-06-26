"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getSnapshot, importResult, jobDownloadUrl, startExport } from "@gulp/api-client";
import type { Snapshot } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import { exportOutcome } from "@/lib/export";

const POLL_MS = 3000;
const MAX_POLLS = 40;

/** Pull the built job archive to the user's machine without navigating away. */
function downloadJob(id: string) {
  const a = document.createElement("a");
  a.href = jobDownloadUrl(id); // server sends Content-Disposition: attachment
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function ExportActions({ id, status }: { id: string; status: Snapshot["status"] }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // While the worker builds the job, poll until the snapshot leaves `unprocessed`.
  // On success → auto-download the tar; on failure → surface the reason.
  useEffect(() => {
    if (!building) return;
    let polls = 0;
    const timer = setInterval(async () => {
      polls += 1;
      try {
        const snap = await getSnapshot(id);
        const outcome = exportOutcome(snap.status);
        if (outcome.state === "ready") {
          clearInterval(timer);
          setBuilding(false);
          downloadJob(id);
          router.refresh();
          return;
        }
        if (outcome.state === "failed") {
          clearInterval(timer);
          setBuilding(false);
          setError(outcome.message);
          router.refresh();
          return;
        }
      } catch {
        // transient — keep polling until the cap
      }
      if (polls >= MAX_POLLS) {
        clearInterval(timer);
        setBuilding(false);
        setError("Export timed out — please try again.");
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [building, id, router]);

  async function onExport() {
    setBusy(true);
    setError(null);
    try {
      await startExport(id);
      setBuilding(true);
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      await importResult(id, file);
    } catch (err) {
      alert(String(err));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
      router.refresh();
      setBusy(false);
    }
  }

  if (status === "exported") {
    return (
      <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
        <a href={jobDownloadUrl(id)}><Button variant="secondary">⤓ Download job</Button></a>
        <Button variant="secondary" disabled={busy} onClick={() => fileRef.current?.click()}>⤓ Upload result</Button>
        <input ref={fileRef} type="file" accept=".zip" hidden onChange={onUpload} />
      </span>
    );
  }
  return (
    <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
      <Button variant="secondary" disabled={busy || building} onClick={onExport}>
        {building ? "Preparing export…" : error ? "⇪ Retry export" : "⇪ Export job"}
      </Button>
      {error && (
        <span role="alert" style={{ color: "var(--color-danger, #c0362c)", fontSize: 13 }}>
          {error}
        </span>
      )}
    </span>
  );
}
