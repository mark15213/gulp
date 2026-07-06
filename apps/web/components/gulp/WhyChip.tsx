"use client";

import React, { useState } from "react";
import type { SessionCard } from "@gulp/api-client";
import styles from "./Gulp.module.css";

// The scheduler's reasoning for surfacing this card now (S4 §7, prototype's
// `.why`/`.whypop`). Collapsed by default — the copy is a footnote, not
// something that should compete with the prompt above it.
const REASON_COPY: Record<SessionCard["reason"], string> = {
  new: "New card",
  due: "Came due for review",
  retest: "You just missed this — another pass",
  at_risk: "Overdue — at risk of forgetting",
};

export function WhyChip({ reason }: { reason: SessionCard["reason"] }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        className={styles.whyBtn}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        why am I seeing this?
      </button>
      {open && <p className={styles.whyPop}>{REASON_COPY[reason]}</p>}
    </>
  );
}
