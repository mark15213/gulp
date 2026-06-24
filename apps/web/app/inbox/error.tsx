"use client";

export default function InboxError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div style={{ padding: 24 }}>
      <h1 className="t-title-l">Inbox</h1>
      <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>
        Couldn&apos;t load your inbox. Please try again.
      </p>
      <button onClick={reset} style={{ marginTop: 12 }}>Retry</button>
    </div>
  );
}
