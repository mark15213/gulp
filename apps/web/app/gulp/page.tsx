"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  getCurrentGulpSession,
  startGulpSession,
  type GulpSession,
} from "@gulp/api-client";
import { SessionRunner } from "@/components/gulp/SessionRunner";
import styles from "@/components/gulp/Gulp.module.css";

// The /gulp entry (S4 §7): resume today's in-progress session if one
// exists, else start a fresh daily session, then hand off to the
// SessionRunner state machine. Full-bleed — the sidebar is hidden by
// Shell's route-aware chrome gate (components/shell/FullBleedGate.tsx).
export default function GulpPage() {
  const [session, setSession] = useState<GulpSession | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Guards against React Strict Mode's double-invoked mount effect, which
  // would otherwise fire two POST /gulp/sessions calls. Deliberately not
  // paired with an abort/"cancelled" flag on cleanup: Strict Mode's fake
  // unmount would set that flag before the in-flight request resolves,
  // permanently blocking the state update the *second* (real) mount is
  // waiting on. The ref alone is enough — it stops a second request from
  // ever starting; the first one is left to resolve normally.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    (async () => {
      try {
        const current = await getCurrentGulpSession();
        const next = current ?? (await startGulpSession({ scope_type: "daily" }));
        setSession(next);
      } catch {
        setError("Couldn't start today's session — try again.");
      }
    })();
  }, []);

  if (error) {
    return (
      <div className={styles.loading} role="alert">
        {error}
      </div>
    );
  }

  if (!session) {
    return (
      <div className={styles.loading} aria-live="polite">
        Preparing today&apos;s gulp…
      </div>
    );
  }

  return <SessionRunner initial={session} />;
}
