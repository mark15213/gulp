"use client";

import React, { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function TableEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "table" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [headers, setHeaders] = useState<string[]>(block.headers);
  const [rows, setRows] = useState<string[][]>(block.rows.map((r) => r.slice()));
  const [caption, setCaption] = useState(block.caption ?? "");
  const cols = headers.length;

  function setHeader(c: number, v: string) {
    setHeaders(headers.map((h, i) => (i === c ? v : h)));
  }
  function setCell(r: number, c: number, v: string) {
    setRows(rows.map((row, ri) => (ri === r ? row.map((cell, ci) => (ci === c ? v : cell)) : row)));
  }
  function addRow() {
    setRows([...rows, Array(cols).fill("")]);
  }
  function addColumn() {
    setHeaders([...headers, `Column ${cols + 1}`]);
    setRows(rows.map((row) => [...row, ""]));
  }
  function save() {
    onSave({ type: "table", headers, rows, caption: caption.trim() ? caption : null });
  }

  return (
    <EditorShell onSave={save} onCancel={onCancel}>
      <table className={styles.grid}>
        <thead>
          <tr>
            {headers.map((h, c) => (
              <td key={c}>
                <input
                  className={styles.input}
                  aria-label={`header ${c}`}
                  value={h}
                  onChange={(e) => setHeader(c, e.target.value)}
                />
              </td>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) => (
                <td key={c}>
                  <input
                    className={styles.input}
                    aria-label={`cell ${r},${c}`}
                    value={cell}
                    onChange={(e) => setCell(r, c, e.target.value)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className={styles.actions}>
        <button type="button" className={styles.iconBtn} onClick={addRow}>
          Add row
        </button>
        <button type="button" className={styles.iconBtn} onClick={addColumn}>
          Add column
        </button>
      </div>
      <div className={styles.field}>
        <label htmlFor="table-caption">Caption</label>
        <input
          id="table-caption"
          aria-label="Caption"
          className={styles.input}
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
        />
      </div>
    </EditorShell>
  );
}
