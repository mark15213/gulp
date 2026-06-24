import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { CaptureProvider } from "@/components/capture/CaptureProvider";
import { CaptureButton } from "@/components/capture/CaptureButton";
import styles from "./Shell.module.css";

// The web workbench frame (docs/03 §5.2): fixed sidebar + fluid content.
export function Shell({ children }: { children: ReactNode }) {
  return (
    <CaptureProvider>
      <div className={styles.shell}>
        <Sidebar />
        <main className={styles.main}>
          <div style={{ display: "flex", justifyContent: "flex-end", padding: "12px 24px 0" }}>
            <CaptureButton />
          </div>
          {children}
        </main>
      </div>
    </CaptureProvider>
  );
}
