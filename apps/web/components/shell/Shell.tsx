import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import styles from "./Shell.module.css";

// The web workbench frame (docs/03 §5.2): fixed sidebar + fluid content.
export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <main className={styles.main}>{children}</main>
    </div>
  );
}
