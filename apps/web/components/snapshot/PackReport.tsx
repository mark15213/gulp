import React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import type { PackOut } from "@gulp/api-client";
import { BlockCell } from "./BlockCell";
import styles from "./PackReport.module.css";

type Block = PackOut["sections"][number]["blocks"][number];

function Md({ children }: { children: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
      {children}
    </Markdown>
  );
}

function BlockView({ block }: { block: Block }) {
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
          <div className={styles.figureLabel}>{block.label}</div>
          <div className={styles.explanation}>{block.explanation}</div>
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

export function PackReport({ pack }: { pack: PackOut }) {
  return (
    <article className={styles.report}>
      <h1 className={`t-display ${styles.title}`}>{pack.title}</h1>

      {pack.core_contributions.length > 0 && (
        <section className={styles.block}>
          <p className={`t-label ${styles.overline}`}>CORE CONTRIBUTIONS</p>
          <ul className={styles.contribList}>
            {pack.core_contributions.map((c, i) => (
              <li key={i}>
                <Md>{c}</Md>
              </li>
            ))}
          </ul>
        </section>
      )}

      {pack.key_insight && (
        <section className={styles.insight}>
          <p className={`t-label ${styles.overline}`}>KEY INSIGHT</p>
          <div className={`t-body-l ${styles.insightBody}`}>
            <Md>{pack.key_insight}</Md>
          </div>
        </section>
      )}

      {pack.sections.map((section) => (
        <section key={section.id} className={styles.section}>
          {section.heading && <h2 className={`t-title-m ${styles.heading}`}>{section.heading}</h2>}
          {section.blocks.map((block) => (
            <BlockCell key={block.id} id={block.id}>
              <BlockView block={block} />
            </BlockCell>
          ))}
        </section>
      ))}

      {pack.references.length > 0 && (
        <section className={styles.references}>
          <p className={`t-label ${styles.overline}`}>FURTHER READING</p>
          <ul className={styles.refList}>
            {pack.references.map((r, i) => (
              <li key={i}>
                <span className={styles.refCitation}>{r.citation}</span>
                <span className={styles.refWhy}>{r.why_interesting}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
