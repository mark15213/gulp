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
  // producing a tar: the link was unreachable, OR its format couldn't be read
  // (e.g. a PDF — only HTML pages and notes are supported so far).
  return {
    state: "failed",
    message:
      "Export failed — couldn’t read this source. The link may be unreachable, or its format (e.g. PDF) isn’t supported yet.",
  };
}
