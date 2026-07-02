"use client";

import React, { useState } from "react";
import type { PackOut } from "@gulp/api-client";
import { CardsView } from "@/components/cards/CardsView";
import { PackReport } from "./PackReport";
import styles from "./ReaderToggle.module.css";

type CardsStatus = "generating" | "ready" | "failed" | null;

export function ReaderToggle({
  pack,
  original,
  snapshotId,
  cardsStatus,
}: {
  pack: PackOut;
  original: string | null;
  snapshotId: string;
  cardsStatus: CardsStatus;
}) {
  const [view, setView] = useState<"pack" | "original" | "cards">("pack");
  return (
    <div>
      <div className={styles.bar}>
        <button
          className={`${styles.tab} ${view === "pack" ? styles.active : ""}`}
          onClick={() => setView("pack")}
        >
          Pack
        </button>
        <button
          className={`${styles.tab} ${view === "original" ? styles.active : ""}`}
          onClick={() => setView("original")}
          disabled={!original}
        >
          Original
        </button>
        <button
          className={`${styles.tab} ${view === "cards" ? styles.active : ""}`}
          onClick={() => setView("cards")}
        >
          Cards
        </button>
      </div>
      {view === "pack" && (
        <div className={styles.main}>
          <PackReport pack={pack} />
        </div>
      )}
      {view === "original" && (
        <div className={styles.original}>{original ?? "No original text stored."}</div>
      )}
      {view === "cards" && (
        <div className={styles.main}>
          <CardsView snapshotId={snapshotId} initialCardsStatus={cardsStatus} />
        </div>
      )}
    </div>
  );
}
