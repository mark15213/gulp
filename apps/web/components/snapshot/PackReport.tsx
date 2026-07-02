import React from "react";
import type { PackOut } from "@gulp/api-client";
import { BlockCell } from "./BlockCell";
import { BlockView } from "./BlockView";
import { Md } from "./Md";
import styles from "./PackReport.module.css";

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
