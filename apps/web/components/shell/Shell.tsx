import React from "react";
import type { ReactNode } from "react";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { getMe } from "@/lib/serverApi";
import {
  isPublicAuthPath,
  REQUEST_PATHNAME_HEADER,
} from "@/lib/authRoutes";
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
  const pathname = (await headers()).get(REQUEST_PATHNAME_HEADER);
  const user = await getMe();

  if (!user) {
    // Missing pathname means middleware intentionally excluded this request
    // (for example a static-file 404). Render it without authenticated chrome.
    if (pathname !== null && !isPublicAuthPath(pathname)) redirect("/login");
    return <AuthProvider initialUser={null}>{children}</AuthProvider>;
  }

  if (pathname !== null && isPublicAuthPath(pathname)) redirect("/");

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
