"use client";

import React, { useEffect } from "react";
import styles from "./Gulp.module.css";

type Grade = "got_it" | "fuzzy" | "missed";

const KEY_TO_GRADE: Record<string, Grade> = {
  "1": "got_it",
  "2": "fuzzy",
  "3": "missed",
};

// "How well did you know it?" (S4 §7, prototype's `.gradebar`). Three
// buttons, emerald/amber/red via the `--state-known/learning/risk` tokens,
// plus keys 1/2/3 — guarded so they don't fire while some other input (e.g.
// the cloze box) is focused.
export function GradeBar({
  onGrade,
  suggested,
}: {
  onGrade: (g: Grade) => void;
  suggested?: string;
}) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target && target.tagName === "INPUT") return;
      const grade = KEY_TO_GRADE[e.key];
      if (grade) onGrade(grade);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onGrade]);

  return (
    <div className={styles.gradebar}>
      <div className={styles.grades}>
        <button
          type="button"
          className={`${styles.gradeBtn} ${styles.gradeGot} ${
            suggested === "got_it" ? styles.suggested : ""
          }`}
          onClick={() => onGrade("got_it")}
        >
          <span className={styles.gradeLabel}>
            Got it <span className={styles.gradeKey}>1</span>
          </span>
        </button>
        <button
          type="button"
          className={`${styles.gradeBtn} ${styles.gradeFuzzy}`}
          onClick={() => onGrade("fuzzy")}
        >
          <span className={styles.gradeLabel}>
            Fuzzy <span className={styles.gradeKey}>2</span>
          </span>
        </button>
        <button
          type="button"
          className={`${styles.gradeBtn} ${styles.gradeMiss} ${
            suggested === "missed" ? styles.suggested : ""
          }`}
          onClick={() => onGrade("missed")}
        >
          <span className={styles.gradeLabel}>
            Missed <span className={styles.gradeKey}>3</span>
          </span>
        </button>
      </div>
    </div>
  );
}
