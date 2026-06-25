"use client";

import { useState } from "react";
import type { PackOut } from "@gulp/api-client";
import { PackReport } from "./PackReport";
import { FacetRail } from "./FacetRail";
import styles from "./ReaderToggle.module.css";

export function ReaderToggle({ pack, original }: { pack: PackOut; original: string | null }) {
  const [view, setView] = useState<"pack" | "original">("pack");
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
      </div>
      {view === "pack" ? (
        <div className={styles.layout}>
          <div className={styles.main}>
            <PackReport pack={pack} />
          </div>
          <div className={styles.rail}>
            <FacetRail facets={pack.facets} />
          </div>
        </div>
      ) : (
        <div className={styles.original}>{original ?? "No original text stored."}</div>
      )}
    </div>
  );
}
