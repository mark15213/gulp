"use client";

import React, { useState } from "react";
import type { PackOut } from "@gulp/api-client";
import { CardsView } from "@/components/cards/CardsView";
import { PackReport } from "./PackReport";
import styles from "./ReaderToggle.module.css";

type CardsStatus = "generating" | "ready" | "failed" | null;

export function ReaderToggle({
  pack,
  snapshotId,
  cardsStatus,
}: {
  pack: PackOut;
  snapshotId: string;
  cardsStatus: CardsStatus;
}) {
  const [view, setView] = useState<"pack" | "cards">("pack");
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
      {view === "cards" && (
        <div className={styles.main}>
          <CardsView snapshotId={snapshotId} initialCardsStatus={cardsStatus} />
        </div>
      )}
    </div>
  );
}
