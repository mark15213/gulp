import React from "react";
import type { TodayOut } from "@gulp/api-client";
import { StateChip } from "@/components/ui/StateChip";
import styles from "./MasteryTally.module.css";

// The Today mastery tally (docs/03 §7.9, S4 §7 prototype's `.tally` strip):
// four counted state chips summarizing the whole library's ladder position,
// not just what's due today.
export function MasteryTally({ mastery }: { mastery: TodayOut["mastery"] }) {
  return (
    <div className={styles.tally}>
      <StateChip state="known" count={mastery.known} />
      <StateChip state="learning" count={mastery.learning} />
      <StateChip state="new" count={mastery.new} />
      <StateChip state="at-risk" count={mastery.at_risk} />
    </div>
  );
}
