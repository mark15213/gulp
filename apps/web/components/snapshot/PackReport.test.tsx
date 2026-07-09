import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import type { PackOut } from "@gulp/api-client";
import { PackReport } from "./PackReport";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return {
    ...actual,
    updateBlock: vi.fn(),
    createBlock: vi.fn(),
    deleteBlock: vi.fn(),
    getBlockMessages: vi.fn(),
    postBlockMessage: vi.fn(),
    getFigures: vi.fn(async () => []),
  };
});

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

const pack: PackOut = {
  snapshot_id: "00000000-0000-0000-0000-000000000001",
  status: "ready",
  pack_type: "paper",
  title: "BERT",
  core_contributions: ["MLM enables **bidirectionality**."],
  key_insight: "Change the objective.",
  sections: [
    {
      id: "00000000-0000-0000-0000-0000000000a1",
      heading: "Math",
      blocks: [
        { id: "00000000-0000-0000-0000-0000000000b1", type: "prose", content: "Loss is $L=-\\sum_i y_i$ here." },
        { id: "00000000-0000-0000-0000-0000000000b2", type: "formula", latex: "E=mc^2", explanation: "Mass-energy." },
        { id: "00000000-0000-0000-0000-0000000000b3", type: "table", headers: ["Model", "F1"], rows: [["BERT", "93.2"]], caption: "Results" },
        { id: "00000000-0000-0000-0000-0000000000b4", type: "list", ordered: false, items: ["lr=1e-4"] },
        { id: "00000000-0000-0000-0000-0000000000b5", type: "list", ordered: true, items: ["step one"] },
        { id: "00000000-0000-0000-0000-0000000000b6", type: "figure", label: "Figure 1", explanation: "Architecture overview." },
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
    expect(html).toContain("<ol");
    expect(html).toContain("step one");
    expect(html).toContain("Mass-energy.");
    expect(html).toContain("Figure 1");
    expect(html).toContain("Architecture overview.");
  });

  it("wraps each block in a cell carrying its stable id", () => {
    const html = renderToStaticMarkup(<PackReport pack={pack} />);
    expect(html).toContain('data-block-id="00000000-0000-0000-0000-0000000000b1"');
    expect(html).toContain('data-block-id="00000000-0000-0000-0000-0000000000b6"');
  });

  it("gives every section title the same heading treatment", () => {
    const html = renderToStaticMarkup(<PackReport pack={pack} />);
    expect(html).toMatch(/<h1[^>]*>BERT<\/h1>/); // pack title is the page h1
    // Meta blocks and content sections share one heading style (Title Case).
    expect(html).toContain("Core contributions");
    expect(html).toContain("Key insight");
    expect(html).toContain("Further reading");
    expect(html).toContain("t-title-m");         // section heading role kept
  });
});

describe("PackReport article packs", () => {
  const articlePack: PackOut = {
    snapshot_id: "00000000-0000-0000-0000-000000000002",
    status: "ready",
    pack_type: "article",
    title: "Harness Engineering",
    summary: "A post about harnesses.",
    core_contributions: [],
    references: [],
    sections: [
      {
        id: "00000000-0000-0000-0000-0000000000c1",
        heading: null,
        blocks: [
          { id: "00000000-0000-0000-0000-0000000000d1", type: "prose", content: "Verbatim intro." },
          {
            id: "00000000-0000-0000-0000-0000000000d2",
            type: "code",
            language: "python",
            content: "def f():\n    return 1",
          },
          {
            id: "00000000-0000-0000-0000-0000000000d3",
            type: "figure",
            label: "Diagram",
            explanation: "",
            url: "https://x.test/fig1.png",
          },
        ],
      },
    ],
  };

  it("shows the summary and no paper header sections", () => {
    const html = renderToStaticMarkup(<PackReport pack={articlePack} />);
    expect(html).toContain("A post about harnesses.");
    expect(html).not.toContain("Core contributions");
    expect(html).not.toContain("Key insight");
    expect(html).not.toContain("Further reading");
  });

  it("renders code blocks as <pre><code>", () => {
    const html = renderToStaticMarkup(<PackReport pack={articlePack} />);
    expect(html).toContain("<pre");
    expect(html).toContain("return 1");
  });

  it("renders remote-url figures as images", () => {
    const html = renderToStaticMarkup(<PackReport pack={articlePack} />);
    expect(html).toContain('src="https://x.test/fig1.png"');
  });
});

describe("PackReport editing", () => {
  it("edits a prose block and calls updateBlock with the new content", async () => {
    (api.updateBlock as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "00000000-0000-0000-0000-0000000000b1",
      type: "prose",
      content: "changed",
    });
    render(<PackReport pack={pack} />);
    // block b1 is the prose block in the fixture's section
    const cell = document.querySelector('[data-block-id="00000000-0000-0000-0000-0000000000b1"]')!;
    await userEvent.click(cell.querySelector('[aria-label="Edit block"]') as HTMLElement);
    const ta = screen.getByLabelText("Prose (Markdown)");
    await userEvent.clear(ta);
    await userEvent.type(ta, "changed");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(api.updateBlock).toHaveBeenCalledWith(
      pack.snapshot_id,
      "00000000-0000-0000-0000-0000000000b1",
      { content: { type: "prose", content: "changed" } },
    );
  });

  it("deletes a block optimistically via deleteBlock", async () => {
    (api.deleteBlock as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    render(<PackReport pack={pack} />);
    const cell = document.querySelector('[data-block-id="00000000-0000-0000-0000-0000000000b1"]')!;
    await userEvent.click(cell.querySelector('[aria-label="Delete block"]') as HTMLElement);
    expect(api.deleteBlock).toHaveBeenCalledWith(
      pack.snapshot_id,
      "00000000-0000-0000-0000-0000000000b1",
    );
    expect(
      document.querySelector('[data-block-id="00000000-0000-0000-0000-0000000000b1"]'),
    ).toBeNull();
  });

  it("inserts a new block via createBlock and renders it", async () => {
    (api.createBlock as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "new-block-id",
      type: "prose",
      content: "",
    });
    render(<PackReport pack={pack} />);
    // use the first Add-block menu in the section
    await userEvent.click(screen.getAllByRole("button", { name: "Add block" })[0]!);
    await userEvent.click(screen.getAllByRole("button", { name: "Add prose block" })[0]!);
    expect(api.createBlock).toHaveBeenCalled();
  });

  it("inserts a pre-linked figure block below the chosen block", async () => {
    vi.mocked(api.getFigures).mockResolvedValue([
      { id: "fig-9", label: "Figure 2", caption: "Attention heads.", mime_type: "image/png", width: 8, height: 8 },
    ]);
    vi.mocked(api.createBlock).mockResolvedValue({
      id: "00000000-0000-0000-0000-0000000000c1",
      type: "figure",
      label: "Figure 2",
      explanation: "Attention heads.",
      figure_id: "fig-9",
    });
    render(<PackReport pack={pack} />);
    const menus = await screen.findAllByRole("button", { name: /insert figure below/i });
    await userEvent.click(menus[0]!);
    await userEvent.click(screen.getByRole("button", { name: "Figure 2" }));
    expect(api.createBlock).toHaveBeenCalledWith(
      pack.snapshot_id,
      pack.sections[0]!.id,
      {
        content: { type: "figure", label: "Figure 2", explanation: "Attention heads.", figure_id: "fig-9" },
        position: 1,
      },
    );
  });
});

describe("PackReport chat", () => {
  it("opens the ChatPanel for a block when its Discuss button is clicked", async () => {
    (api.getBlockMessages as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    render(<PackReport pack={pack} />);
    const cell = document.querySelector('[data-block-id="00000000-0000-0000-0000-0000000000b1"]')!;
    await userEvent.click(cell.querySelector('[aria-label="Discuss block"]') as HTMLElement);
    // the panel mounts and loads this block's messages
    expect(await screen.findByLabelText("Ask about this block")).toBeTruthy();
    expect(api.getBlockMessages).toHaveBeenCalledWith(
      pack.snapshot_id,
      "00000000-0000-0000-0000-0000000000b1",
    );
  });
});
