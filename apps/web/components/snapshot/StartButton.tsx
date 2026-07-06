"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { startProcessing } from "@gulp/api-client";
import { IconButton } from "@/components/ui/IconButton";
import { IconPlay } from "@/components/ui/icons";

export function StartButton({ id, label = "Start" }: { id: string; label?: string }) {
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
    <IconButton label={pending ? "Starting…" : label} onClick={onClick} disabled={pending}>
      <IconPlay />
    </IconButton>
  );
}
