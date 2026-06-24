// Root layout — placeholder shell. S0 Foundation fills in the web sidebar nav (docs/01 §4.3).
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
