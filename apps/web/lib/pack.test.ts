import { describe, expect, it } from "vitest";
import { groupFacets, isProcessing } from "./pack";
import type { PackOut } from "@gulp/api-client";

type Facet = PackOut["facets"][number];

const facets: Facet[] = [
  { element_type: "claim", text: "c1" },
  { element_type: "key_term", text: "t1" },
  { element_type: "claim", text: "c2" },
];

describe("groupFacets", () => {
  it("orders groups and keeps only non-empty ones", () => {
    const groups = groupFacets(facets);
    expect(groups.map((g) => g.type)).toEqual(["key_term", "claim"]); // FACET_ORDER, no empties
    expect(groups[0].label).toBe("Key terms");
    expect(groups[1].items.map((f) => f.text)).toEqual(["c1", "c2"]);
  });

  it("returns [] for no facets", () => {
    expect(groupFacets([])).toEqual([]);
  });
});

describe("isProcessing", () => {
  it("is true only for processing", () => {
    expect(isProcessing("processing")).toBe(true);
    expect(isProcessing("ready")).toBe(false);
    expect(isProcessing("needs_attention")).toBe(false);
  });
});
