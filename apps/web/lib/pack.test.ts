import { describe, expect, it } from "vitest";
import { groupFacets, isProcessing, safeHost, statusLabel } from "./pack";
import type { PackOut } from "@gulp/api-client";
import type { Facet } from "./pack";

type _Facet = PackOut["facets"][number];

const facets: Facet[] = [
  { element_type: "claim", text: "c1" },
  { element_type: "key_term", text: "t1" },
  { element_type: "claim", text: "c2" },
];

describe("groupFacets", () => {
  it("orders groups and keeps only non-empty ones", () => {
    const groups = groupFacets(facets);
    expect(groups.map((g) => g.type)).toEqual(["key_term", "claim"]); // FACET_ORDER, no empties
    expect(groups[0]!.label).toBe("Key terms");
    expect(groups[1]!.items.map((f) => f.text)).toEqual(["c1", "c2"]);
  });

  it("returns [] for no facets", () => {
    expect(groupFacets([])).toEqual([]);
  });

  it("excludes null-text facets", () => {
    const withNull: Facet[] = [
      { element_type: "claim", text: "c1" },
      { element_type: "claim", text: null } as Facet,
    ];
    const groups = groupFacets(withNull);
    expect(groups[0]!.items).toHaveLength(1);
    expect(groups[0]!.items[0]!.text).toBe("c1");
  });
});

describe("isProcessing", () => {
  it("is true only for processing", () => {
    expect(isProcessing("processing")).toBe(true);
    expect(isProcessing("ready")).toBe(false);
    expect(isProcessing("needs_attention")).toBe(false);
  });

  it("is true for queued", () => {
    expect(isProcessing("queued")).toBe(true);
  });
});

describe("statusLabel", () => {
  it("labels exported and the rest", () => {
    expect(statusLabel("exported")).toBe("Exported");
    expect(statusLabel("ready")).toBe("Ready");
    expect(statusLabel("unprocessed")).toBe("Not started");
  });
});

describe("safeHost", () => {
  it("returns host for a valid URL", () => {
    expect(safeHost("https://example.com/x")).toBe("example.com");
  });

  it("returns Note for a schemeless URL", () => {
    expect(safeHost("example.com")).toBe("Note");
  });

  it("returns Note for null", () => {
    expect(safeHost(null)).toBe("Note");
  });
});
