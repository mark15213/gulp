"use client";

import React, { useState } from "react";
import { updateSnapshot } from "@gulp/api-client";
import type { SourceGenre } from "@gulp/api-client";
import styles from "./GenreSelect.module.css";

const GENRES: SourceGenre[] = ["paper", "article", "note"];

// The detected knowledge genre — user-correctable; a change takes effect on
// the next processing run (the strategy is selected by genre).
export function GenreSelect({
  snapshotId,
  genre: initialGenre,
}: {
  snapshotId: string;
  genre: SourceGenre | null;
}) {
  const [genre, setGenre] = useState<SourceGenre | null>(initialGenre);
  const [hint, setHint] = useState<string | null>(null);

  function change(next: SourceGenre) {
    const prev = genre;
    setGenre(next);
    setHint(null);
    updateSnapshot(snapshotId, { genre: next })
      .then(() => setHint("Genre updated — re-run processing to apply it."))
      .catch(() => {
        setGenre(prev);
        setHint("Couldn't update the genre — try again.");
      });
  }

  return (
    <span className={styles.wrap}>
      <label className={styles.label} htmlFor="genre-select">
        Genre
      </label>
      <select
        id="genre-select"
        aria-label="Genre"
        className={styles.select}
        value={genre ?? ""}
        onChange={(e) => change(e.target.value as SourceGenre)}
      >
        {genre === null && <option value="">unclassified</option>}
        {GENRES.map((g) => (
          <option key={g} value={g}>
            {g}
          </option>
        ))}
      </select>
      {hint && <span className={styles.hint}>{hint}</span>}
    </span>
  );
}
