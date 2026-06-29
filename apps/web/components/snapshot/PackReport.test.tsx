import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { PackOut } from "@gulp/api-client";
import { PackReport } from "./PackReport";

const pack: PackOut = {
  snapshot_id: "00000000-0000-0000-0000-000000000001",
  status: "ready",
  title: "BERT",
  core_contributions: ["MLM enables **bidirectionality**."],
  key_insight: "Change the objective.",
  sections: [
    {
      heading: "Math",
      blocks: [
        { type: "prose", content: "Loss is $L=-\\sum_i y_i$ here." },
        { type: "formula", latex: "E=mc^2", explanation: "Mass-energy." },
        { type: "table", headers: ["Model", "F1"], rows: [["BERT", "93.2"]], caption: "Results" },
        { type: "list", ordered: false, items: ["lr=1e-4"] },
        { type: "figure", label: "Figure 1", explanation: "Architecture overview." },
      ],
    },
  ],
  references: [{ citation: "Vaswani 2017", why_interesting: "Transformer." }],
};

describe("PackReport", () => {
  it("renders title, contributions, key insight and references", () => {
    const html = renderToStaticMarkup(<PackReport pack={pack} />);
    expect(html).toContain("BERT");
    expect(html).toContain("Core contributions");
    expect(html).toContain("<strong>bidirectionality</strong>");
    expect(html).toContain("Key insight");
    expect(html).toContain("Vaswani 2017");
  });

  it("renders typed blocks: math via KaTeX, real tables, lists, figures", () => {
    const html = renderToStaticMarkup(<PackReport pack={pack} />);
    expect(html).toContain("katex"); // rehype-katex typeset both inline and display math
    expect(html).toContain("<table");
    expect(html).toContain("93.2");
    expect(html).toContain("Results");
    expect(html).toContain("lr=1e-4");
    expect(html).toContain("Figure 1");
    expect(html).toContain("Architecture overview.");
  });
});
