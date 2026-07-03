import type { BlockUpdateBody, PackBlockOut, PackOut } from "@gulp/api-client";

export type BlockWrite = NonNullable<BlockUpdateBody["content"]>;
export type BlockType = PackBlockOut["type"];

type Section = PackOut["sections"][number];

function mapSection(pack: PackOut, sectionId: string, fn: (s: Section) => Section): PackOut {
  return {
    ...pack,
    sections: pack.sections.map((s) => (s.id === sectionId ? fn(s) : s)),
  };
}

export function replaceBlock(
  pack: PackOut,
  sectionId: string,
  blockId: string,
  block: PackBlockOut,
): PackOut {
  return mapSection(pack, sectionId, (s) => ({
    ...s,
    blocks: s.blocks.map((b) => (b.id === blockId ? block : b)),
  }));
}

export function removeBlock(pack: PackOut, sectionId: string, blockId: string): PackOut {
  return mapSection(pack, sectionId, (s) => ({
    ...s,
    blocks: s.blocks.filter((b) => b.id !== blockId),
  }));
}

export function insertBlockAt(
  pack: PackOut,
  sectionId: string,
  index: number,
  block: PackBlockOut,
): PackOut {
  return mapSection(pack, sectionId, (s) => {
    const blocks = s.blocks.slice();
    const i = Math.max(0, Math.min(index, blocks.length));
    blocks.splice(i, 0, block);
    return { ...s, blocks };
  });
}

export function moveBlock(
  pack: PackOut,
  sectionId: string,
  blockId: string,
  newIndex: number,
): PackOut {
  return mapSection(pack, sectionId, (s) => {
    const blocks = s.blocks.filter((b) => b.id !== blockId);
    const moved = s.blocks.find((b) => b.id === blockId);
    if (!moved) return s;
    const i = Math.max(0, Math.min(newIndex, blocks.length));
    blocks.splice(i, 0, moved);
    return { ...s, blocks };
  });
}

export function emptyContent(type: BlockType): BlockWrite {
  switch (type) {
    case "prose":
      return { type: "prose", content: "" };
    case "formula":
      return { type: "formula", latex: "", explanation: "" };
    case "table":
      return { type: "table", headers: ["Column 1", "Column 2"], rows: [["", ""]], caption: null };
    case "figure":
      return { type: "figure", label: "", explanation: "", figure_id: null };
    case "list":
      return { type: "list", items: [""], ordered: false };
  }
}
