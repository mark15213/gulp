import type { Snapshot } from "@gulp/api-client";

/**
 * What a build-export poll tick means for the UI.
 * - `pending`  — the worker is still building (snapshot still `unprocessed`)
 * - `ready`    — the job archive is built (`exported`); auto-download it
 * - `failed`   — the build errored out (e.g. the source URL couldn't be fetched),
 *                so no archive exists; show the message instead of silently reverting
 */
export type ExportPollOutcome =
  | { state: "pending" }
  | { state: "ready" }
  | { state: "failed"; message: string };

export function exportOutcome(status: Snapshot["status"]): ExportPollOutcome {
  if (status === "unprocessed") return { state: "pending" };
  if (status === "exported") return { state: "ready" };
  // Any other status the build lands in (needs_attention) means it failed before
  // producing a tar — the most common cause is the source page not being fetchable.
  return {
    state: "failed",
    message: "Export failed — the source couldn’t be fetched. Check the link and try again.",
  };
}
