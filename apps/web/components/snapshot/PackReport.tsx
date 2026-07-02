"use client";

import React, { Fragment, useState } from "react";
import { createBlock, deleteBlock, updateBlock } from "@gulp/api-client";
import type { PackBlockOut, PackOut } from "@gulp/api-client";
import {
  emptyContent,
  insertBlockAt,
  moveBlock,
  removeBlock,
  replaceBlock,
  type BlockType,
  type BlockWrite,
} from "@/lib/packEdit";
import { BlockCell } from "./BlockCell";
import { AddBlockMenu } from "./AddBlockMenu";
import { ChatPanel } from "./ChatPanel";
import { Md } from "./Md";
import styles from "./PackReport.module.css";

export function PackReport({ pack: initialPack }: { pack: PackOut }) {
  const [pack, setPack] = useState(initialPack);
  const [error, setError] = useState<string | null>(null);
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const sid = pack.snapshot_id;

  function saveContent(sectionId: string, blockId: string, content: BlockWrite) {
    setError(null);
    const prev = pack;
    const edited = { ...content, id: blockId } as PackBlockOut;
    setPack(replaceBlock(pack, sectionId, blockId, edited));
    updateBlock(sid, blockId, { content }).catch(() => {
      setPack(prev);
      setError("Couldn't save your edit — try again.");
    });
  }

  function del(sectionId: string, blockId: string) {
    setError(null);
    const prev = pack;
    setPack(removeBlock(pack, sectionId, blockId));
    deleteBlock(sid, blockId).catch(() => {
      setPack(prev);
      setError("Couldn't delete that block — try again.");
    });
  }

  function move(sectionId: string, blockId: string, dir: -1 | 1) {
    setError(null);
    const section = pack.sections.find((s) => s.id === sectionId);
    if (!section) return;
    const i = section.blocks.findIndex((b) => b.id === blockId);
    const newIndex = i + dir;
    if (newIndex < 0 || newIndex >= section.blocks.length) return;
    const prev = pack;
    setPack(moveBlock(pack, sectionId, blockId, newIndex));
    updateBlock(sid, blockId, { position: newIndex }).catch(() => {
      setPack(prev);
      setError("Couldn't reorder — try again.");
    });
  }

  function insert(sectionId: string, index: number, type: BlockType) {
    setError(null);
    createBlock(sid, sectionId, { content: emptyContent(type), position: index })
      .then((block) => setPack((p) => insertBlockAt(p, sectionId, index, block)))
      .catch(() => setError("Couldn't add a block — try again."));
  }

  return (
    <>
      <article className={styles.report}>
        {error && (
          <div className={styles.errorBar} role="alert">
            {error} <button type="button" onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

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
            <AddBlockMenu onInsert={(t) => insert(section.id, 0, t)} />
            {section.blocks.map((block, i) => (
              <Fragment key={block.id}>
                <BlockCell
                  block={block}
                  canMoveUp={i > 0}
                  canMoveDown={i < section.blocks.length - 1}
                  onSaveContent={(content) => saveContent(section.id, block.id, content)}
                  onDelete={() => del(section.id, block.id)}
                  onMoveUp={() => move(section.id, block.id, -1)}
                  onMoveDown={() => move(section.id, block.id, 1)}
                  onDiscuss={() => setSelectedBlockId(block.id)}
                />
                <AddBlockMenu onInsert={(t) => insert(section.id, i + 1, t)} />
              </Fragment>
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
      {selectedBlockId && (
        <ChatPanel
          key={selectedBlockId}
          snapshotId={sid}
          blockId={selectedBlockId}
          onClose={() => setSelectedBlockId(null)}
        />
      )}
    </>
  );
}
