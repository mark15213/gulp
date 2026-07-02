import { describe, expect, it } from "vitest";
import type { PackOut } from "@gulp/api-client";
import { emptyContent, insertBlockAt, moveBlock, removeBlock, replaceBlock } from "./packEdit";

const S = "00000000-0000-0000-0000-0000000000a1";
const B0 = "00000000-0000-0000-0000-0000000000b0";
const B1 = "00000000-0000-0000-0000-0000000000b1";

function pack(): PackOut {
  return {
    snapshot_id: "00000000-0000-0000-0000-000000000001",
    status: "ready",
    title: "T",
    core_contributions: [],
    key_insight: "",
    sections: [
      {
        id: S,
        heading: "H",
        blocks: [
          { id: B0, type: "prose", content: "b0" },
          { id: B1, type: "prose", content: "b1" },
        ],
      },
    ],
    references: [],
  };
}

function ids(p: PackOut): string[] {
  return (p.sections[0]?.blocks ?? []).map((b) => b.id);
}

describe("packEdit", () => {
  it("replaceBlock swaps the matching block, immutably", () => {
    const p0 = pack();
    const p1 = replaceBlock(p0, S, B0, { id: B0, type: "prose", content: "edited" });
    expect(p1).not.toBe(p0);
    expect(p1.sections[0]?.blocks[0]).toEqual({ id: B0, type: "prose", content: "edited" });
    const orig = p0.sections[0]?.blocks[0];
    expect(orig && orig.type === "prose" ? orig.content : null).toBe("b0"); // original untouched
  });

  it("removeBlock drops the matching block, immutably", () => {
    const p0 = pack();
    const p1 = removeBlock(p0, S, B0);
    expect(ids(p1)).toEqual([B1]);
    expect(ids(p0)).toEqual([B0, B1]); // original untouched
  });

  it("insertBlockAt inserts at the index", () => {
    const nb = { id: "new", type: "prose", content: "mid" } as const;
    const p1 = insertBlockAt(pack(), S, 1, nb);
    expect(ids(p1)).toEqual([B0, "new", B1]);
  });

  it("moveBlock reorders within the section (clamped), immutably", () => {
    const p0 = pack();
    const p1 = moveBlock(p0, S, B0, 1);
    expect(ids(p1)).toEqual([B1, B0]);
    expect(ids(p0)).toEqual([B0, B1]); // original untouched
    const p2 = moveBlock(pack(), S, B0, 99);
    expect(ids(p2)).toEqual([B1, B0]);
  });

  it("emptyContent returns a valid fresh write payload per type", () => {
    expect(emptyContent("prose")).toEqual({ type: "prose", content: "" });
    expect(emptyContent("list")).toEqual({ type: "list", items: [""], ordered: false });
    expect(emptyContent("table")).toEqual({
      type: "table",
      headers: ["Column 1", "Column 2"],
      rows: [["", ""]],
      caption: null,
    });
  });
});
