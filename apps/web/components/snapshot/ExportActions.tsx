"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { importResult, jobDownloadUrl, startExport } from "@gulp/api-client";
import type { Snapshot } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";

export function ExportActions({ id, status }: { id: string; status: Snapshot["status"] }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function onExport() {
    setBusy(true);
    try {
      await startExport(id);
    } finally {
      router.refresh();
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
      alert(String(err)); // v1: surface import errors plainly
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
    <Button variant="secondary" disabled={busy} onClick={onExport}>⇪ Export job</Button>
  );
}
