import React from "react";
import type { PackOut } from "@gulp/api-client";
import { groupFacets } from "@/lib/pack";
import styles from "./FacetRail.module.css";

const CHIP_TYPES = new Set(["key_term", "person_org"]);

export function FacetRail({ facets }: { facets: PackOut["facets"] }) {
  const groups = groupFacets(facets);
  if (groups.length === 0) return null;
  return (
    <aside className={styles.rail}>
      {groups.map((group) => (
        <div key={group.type} className={styles.group}>
          <div className={styles.label}>{group.label}</div>
          {CHIP_TYPES.has(group.type) ? (
            <div className={styles.chips}>
              {group.items.map((f, i) => (
                <span key={i} className={styles.chip}>{f.text}</span>
              ))}
            </div>
          ) : (
            group.items.map((f, i) => (
              <p key={i} className={styles.line}>{f.text}</p>
            ))
          )}
        </div>
      ))}
    </aside>
  );
}
