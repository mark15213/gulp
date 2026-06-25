import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { PackOut } from "@gulp/api-client";
import { PackReport } from "./PackReport";
import { FacetRail } from "./FacetRail";

const pack: PackOut = {
  snapshot_id: "00000000-0000-0000-0000-000000000001",
  status: "ready",
  summary: "A short summary.",
  background: "Some background.",
  confidence: 0.8,
  sections: [
    { heading: "Overview", blocks: [{ type: "prose", content: "First paragraph.", anchor_id: "s0b0" }] },
    { heading: "Detail", blocks: [{ type: "quote", content: "A quote.", anchor_id: "s1b0" }] },
  ],
  facets: [
    { element_type: "key_term", text: "attention" },
    { element_type: "claim", text: "Claim one." },
  ],
};

describe("PackReport", () => {
  it("renders summary, headings, and block content", () => {
    const html = renderToStaticMarkup(<PackReport pack={pack} />);
    expect(html).toContain("A short summary.");
    expect(html).toContain("Overview");
    expect(html).toContain("First paragraph.");
    expect(html).toContain("A quote.");
  });
});

describe("FacetRail", () => {
  it("renders grouped facet labels and items", () => {
    const html = renderToStaticMarkup(<FacetRail facets={pack.facets} />);
    expect(html).toContain("Key terms");
    expect(html).toContain("attention");
    expect(html).toContain("Claims");
    expect(html).toContain("Claim one.");
  });
});
