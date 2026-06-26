import type { PackOut, Snapshot } from "@gulp/api-client";

export type Facet = PackOut["facets"][number];
export type ElementType = Facet["element_type"];

const FACET_ORDER: { type: ElementType; label: string }[] = [
  { type: "key_term", label: "Key terms" },
  { type: "person_org", label: "People & orgs" },
  { type: "claim", label: "Claims" },
  { type: "counter_view", label: "Counter-views" },
  { type: "connection", label: "Connections" },
];

export interface FacetGroup {
  type: ElementType;
  label: string;
  items: Facet[];
}

export function groupFacets(facets: Facet[]): FacetGroup[] {
  return FACET_ORDER.map(({ type, label }) => ({
    type,
    label,
    items: facets.filter((f) => f.element_type === type && f.text != null && f.text !== ""),
  })).filter((g) => g.items.length > 0);
}

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
