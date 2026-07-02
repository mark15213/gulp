import React from "react";
import { IconSnapshot, IconConversation, IconSubscription } from "./icons";
import styles from "./ObjectGlyph.module.css";

// Core object taxonomy (docs/03 §2.4) — conversation/subscription arrive in
// later slices; the glyph set is already stable.
export type ObjectType = "snapshot" | "conversation" | "subscription";

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
