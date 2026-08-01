import type { FeedEntry, Snapshot } from "@gulp/api-client";

/** The four stage sections of the merged Inbox (spec 2026-08-01 §4.2).
 *  Order is the belt's order; it is not configurable. */
export type StageKey = "new" | "kept" | "needs" | "flight";

export const STAGES: {
  key: StageKey;
  label: string;
  question: string;
  empty: string;
}[] = [
  {
    key: "new",
    label: "New",
    question: "keep or skip?",
    empty: "Nothing undecided here.",
  },
  {
    key: "kept",
    label: "Kept",
    question: "digest how?",
    empty: "Nothing waiting to be digested.",
  },
  {
    key: "needs",
    label: "Needs you",
    question: "something went sideways",
    empty: "All clear.",
  },
  {
    key: "flight",
    label: "In flight",
    question: "the machine is working",
    empty: "Nothing running.",
  },
];

/** Statuses that never change on their own — stop tracking once reached. */
export const TERMINAL = new Set<Snapshot["status"]>([
  "ready",
  "exported",
  "needs_attention",
]);

export function stageOf(status: Snapshot["status"]): StageKey | null {
  if (status === "unprocessed") return "kept";
  if (status === "exported" || status === "needs_attention") return "needs";
  if (status === "queued" || status === "processing") return "flight";
  return null; // `ready` has left for the Library
}

/** Snapshots that wait on the owner — the sidebar badge (spec §4.5). */
export function isActionable(status: Snapshot["status"]): boolean {
  return status === "unprocessed" || status === "exported" || status === "needs_attention";
}

export type Triage = "pending" | "skipped" | "forwarded";

export function triageOf(entry: FeedEntry): Triage {
  if (entry.promoted_source_id) return "forwarded";
  if (entry.skipped) return "skipped";
  return "pending";
}
