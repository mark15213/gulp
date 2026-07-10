import type { Metadata } from "next";
import type { ReactNode } from "react";
import { geistMono, instrumentSerif } from "./fonts";
import { Shell } from "@/components/shell/Shell";
import { ensureServerApiAuth } from "@/lib/serverApiAuth";
import "@gulp/ui/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gulp",
  description:
    "Forward anything. Gulp turns it into knowledge you can actually remember.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  ensureServerApiAuth();
  return (
    <html
      lang="en"
      className={`${geistMono.variable} ${instrumentSerif.variable}`}
    >
      <head>
        {/* Inter (workhorse, docs/03 §2.3). Non-blocking; falls back to the
            system stack in --font-sans when offline. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
