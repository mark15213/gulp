import React from "react";
import type { PackOut } from "@gulp/api-client";
import styles from "./PackReport.module.css";

const BLOCK_CLASS: Record<string, string | undefined> = {
  prose: styles.prose,
  quote: styles.quote,
  callout: styles.callout,
  figure: styles.callout, // figures deferred — render their text content for now
};

export function PackReport({ pack }: { pack: PackOut }) {
  return (
    <article className={styles.report}>
      <p className={styles.summary}>{pack.summary}</p>
      {pack.background && <p className={styles.background}>{pack.background}</p>}
      {pack.sections.map((section, i) => (
        <section key={i} className={styles.section}>
          {section.heading && <h2 className={styles.heading}>{section.heading}</h2>}
          {section.blocks.map((block) => (
            <p key={block.anchor_id} className={BLOCK_CLASS[block.type] ?? styles.prose}>
              {block.content}
            </p>
          ))}
        </section>
      ))}
    </article>
  );
}
