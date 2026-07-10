import React from "react";
import type { ReactNode } from "react";
import { getMe } from "@gulp/api-client";
import { Sidebar } from "./Sidebar";
import { FullBleedGate } from "./FullBleedGate";
import { AuthProvider } from "@/lib/auth";
import { CaptureProvider } from "@/components/capture/CaptureProvider";
import { CaptureButton } from "@/components/capture/CaptureButton";

// The web workbench frame (docs/03 §5.2): fixed sidebar + fluid content.
// Full-bleed routes (e.g. /gulp, Task 15) opt out of the sidebar + capture
// affordance via FullBleedGate — see that file for why the route check
// lives in a small Client Component rather than here.
export async function Shell({ children }: { children: ReactNode }) {
  const user = await getMe();
  return (
    <AuthProvider initialUser={user}>
      <CaptureProvider>
        <FullBleedGate sidebar={<Sidebar />} captureButton={<CaptureButton />}>
          {children}
        </FullBleedGate>
      </CaptureProvider>
    </AuthProvider>
  );
}
