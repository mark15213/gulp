import React from "react";
import type { ObjectType } from "@/lib/mock";
import { IconSnapshot, IconConversation, IconSubscription } from "./icons";
import styles from "./ObjectGlyph.module.css";

// Stable type glyphs for core objects (docs/03 §2.4/§2.6), in a tinted tile.
const GLYPHS = {
  snapshot: IconSnapshot,
  conversation: IconConversation,
  subscription: IconSubscription,
} as const;

export function ObjectGlyph({ type }: { type: ObjectType }) {
  const Glyph = GLYPHS[type];
  return (
    <span className={styles.glyph}>
      <Glyph />
    </span>
  );
}
