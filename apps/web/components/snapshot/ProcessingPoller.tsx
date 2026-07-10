"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getSnapshot } from "@gulp/api-client";
import { isProcessing } from "@/lib/pack";
import { logError } from "@/lib/logger";

const INTERVAL_MS = 3000;
const MAX_POLLS = 40; // ~2 minutes, then give up (user can refresh)

export function ProcessingPoller({ id }: { id: string }) {
  const router = useRouter();
  useEffect(() => {
    let polls = 0;
    let loggedFailure = false;
    let stopped = false;
    const timer = setInterval(async () => {
      polls += 1;
      try {
        const snap = await getSnapshot(id);
        if (!isProcessing(snap.status)) {
          clearInterval(timer);
          if (!stopped) router.refresh();
        }
      } catch (err) {
        if (!loggedFailure) {
          logError("processing poll failed", err, { snapshotId: id });
          loggedFailure = true;
        }
        // transient — keep polling until the cap
      }
      if (polls >= MAX_POLLS) clearInterval(timer);
    }, INTERVAL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [id, router]);
  return null;
}
