"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { flushQueue } from "@/lib/captureQueue";
import { CaptureSheet } from "./CaptureSheet";

type CaptureCtx = { open: () => void };
const Ctx = createContext<CaptureCtx | null>(null);

export function useCapture(): CaptureCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCapture must be used within CaptureProvider");
  return ctx;
}

export function CaptureProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const router = useRouter();
  const open = useCallback(() => setOpen(true), []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    function drain() {
      void flushQueue().then((n) => {
        if (n > 0) router.refresh();
      });
    }
    drain(); // self-heal on load: recover captures stranded from an earlier failure
    window.addEventListener("online", drain); // and retry when connectivity returns
    return () => window.removeEventListener("online", drain);
  }, [router]);

  return (
    <Ctx.Provider value={{ open }}>
      {children}
      {isOpen && <CaptureSheet onClose={() => setOpen(false)} />}
    </Ctx.Provider>
  );
}
