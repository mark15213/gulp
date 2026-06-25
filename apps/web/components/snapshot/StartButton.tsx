"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { startProcessing } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";

export function StartButton({ id, label = "▶ Start" }: { id: string; label?: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function onClick() {
    setPending(true);
    try {
      await startProcessing(id);
    } catch {
      // 409 = already processing; refreshing reflects the real state either way.
    } finally {
      router.refresh();
      setPending(false);
    }
  }

  return (
    <Button variant="primary" onClick={onClick} disabled={pending}>
      {pending ? "Starting…" : label}
    </Button>
  );
}
