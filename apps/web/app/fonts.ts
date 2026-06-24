import localFont from "next/font/local";

// Geist Mono — the apparatus: counts, intervals, labels (docs/03 §2.3, §4.1).
export const geistMono = localFont({
  src: [
    { path: "./fonts/GeistMono-Regular.ttf", weight: "400", style: "normal" },
    { path: "./fonts/GeistMono-Bold.ttf", weight: "700", style: "normal" },
  ],
  variable: "--font-mono",
  display: "swap",
});

// Instrument Serif — the voice: rationed expressive hero lines (docs/03 §4.2).
export const instrumentSerif = localFont({
  src: [
    {
      path: "./fonts/InstrumentSerif-Regular.ttf",
      weight: "400",
      style: "normal",
    },
    {
      path: "./fonts/InstrumentSerif-Italic.ttf",
      weight: "400",
      style: "italic",
    },
  ],
  variable: "--font-serif",
  display: "swap",
});
