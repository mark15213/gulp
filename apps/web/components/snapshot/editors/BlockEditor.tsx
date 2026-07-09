import React from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { ProseEditor } from "./ProseEditor";
import { FormulaEditor } from "./FormulaEditor";
import { FigureEditor } from "./FigureEditor";
import { ListEditor } from "./ListEditor";
import { TableEditor } from "./TableEditor";
import { CodeEditor } from "./CodeEditor";

export function BlockEditor({
  snapshotId,
  block,
  onSave,
  onCancel,
}: {
  snapshotId: string;
  block: PackBlockOut;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  switch (block.type) {
    case "prose":
      return <ProseEditor block={block} onSave={onSave} onCancel={onCancel} />;
    case "formula":
      return <FormulaEditor block={block} onSave={onSave} onCancel={onCancel} />;
    case "figure":
      return <FigureEditor snapshotId={snapshotId} block={block} onSave={onSave} onCancel={onCancel} />;
    case "list":
      return <ListEditor block={block} onSave={onSave} onCancel={onCancel} />;
    case "table":
      return <TableEditor block={block} onSave={onSave} onCancel={onCancel} />;
    case "code":
      return <CodeEditor block={block} onSave={onSave} onCancel={onCancel} />;
    default:
      return null;
  }
}
