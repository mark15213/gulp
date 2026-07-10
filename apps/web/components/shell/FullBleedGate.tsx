"use client";

import React from "react";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import styles from "./Shell.module.css";

// Routes that render without the app chrome (sidebar + capture affordance) —
// currently just the Gulp session, which needs the full viewport for its
// own full-bleed focus layout (Task 15, S4 §7).
const FULL_BLEED_PREFIXES = ["/gulp", "/snapshots", "/login", "/register"];

function isFullBleed(pathname: string): boolean {
  return FULL_BLEED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

// Shell (a Server Component) resolves `sidebar`/`captureButton` server-side
// and hands them down as already-rendered elements — this Client Component
// only decides, per route, whether to mount them. That split is required by
// the App Router: a Client Component can't import and call an async Server
// Component itself, but it can conditionally render one passed in as a prop.
export function FullBleedGate({
  sidebar,
  captureButton,
  children,
}: {
  sidebar: ReactNode;
  captureButton: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();

  if (isFullBleed(pathname)) {
    return <>{children}</>;
  }

  return (
    <div className={styles.shell}>
      {sidebar}
      <main className={styles.main}>
        <div className={styles.captureRow}>{captureButton}</div>
        {children}
      </main>
    </div>
  );
}
