import React from "react";
import type { PackBlockOut } from "@gulp/api-client";
import { figureUrl } from "@gulp/api-client";
import { Md } from "./Md";
import styles from "./PackReport.module.css";

export function BlockView({ snapshotId, block }: { snapshotId: string; block: PackBlockOut }) {
  switch (block.type) {
    case "prose":
      return (
        <div className={styles.prose}>
          <Md>{block.content}</Md>
        </div>
      );
    case "formula":
      return (
        <figure className={styles.formula}>
          <Md>{`$$\n${block.latex}\n$$`}</Md>
          <figcaption className={styles.explanation}>{block.explanation}</figcaption>
        </figure>
      );
    case "table":
      return (
        <figure className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                {block.headers.map((h, i) => (
                  <th key={i}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, r) => (
                <tr key={r}>
                  {row.map((cell, c) => (
                    <td key={c}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {block.caption && <figcaption className={styles.caption}>{block.caption}</figcaption>}
        </figure>
      );
    case "figure":
      return (
        <figure className={styles.figure}>
          {block.figure_id ? (
            <img
              className={styles.figureImage}
              src={figureUrl(snapshotId, block.figure_id)}
              alt={block.label}
            />
          ) : (
            <div className={styles.figureLabel}>{block.label}</div>
          )}
          <figcaption className={styles.explanation}>{block.explanation}</figcaption>
        </figure>
      );
    case "list":
      return block.ordered ? (
        <ol className={styles.list}>
          {block.items.map((it, i) => (
            <li key={i}>
              <Md>{it}</Md>
            </li>
          ))}
        </ol>
      ) : (
        <ul className={styles.list}>
          {block.items.map((it, i) => (
            <li key={i}>
              <Md>{it}</Md>
            </li>
          ))}
        </ul>
      );
    default:
      return null;
  }
}
