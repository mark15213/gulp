import type { Snapshot } from "@gulp/api-client";

// The poller keeps going while the snapshot is still being processed.
export function isProcessing(status: Snapshot["status"]): boolean {
  return status === "processing" || status === "queued";
}

export function statusLabel(status: Snapshot["status"]): string {
  if (status === "processing" || status === "queued") return "Processing";
  if (status === "needs_attention") return "Needs attention";
  if (status === "unprocessed") return "Not started";
  if (status === "exported") return "Exported";
  return "Ready";
}

// Host label for a source; never throws on a malformed/relative URL.
export function safeHost(url: string | null | undefined): string {
  if (!url) return "Note";
  try {
    return new URL(url).host;
  } catch {
    return "Note";
  }
}
