// Relative "time ago" labels for capture/library rows. Coarse buckets only —
// precision below a minute reads as noise in a list.

const HAS_TZ = /Z$|[+-]\d\d:\d\d$/;

function parseUtc(iso: string): number {
  // The API serializes UTC datetimes; a naive string means UTC, not local.
  return new Date(HAS_TZ.test(iso) ? iso : `${iso}Z`).getTime();
}

export function timeAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.max(0, Math.floor((now.getTime() - parseUtc(iso)) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days}d ago`;
  return new Date(parseUtc(iso)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
