// Thin offline-capture queue (spec C3): optimistic localStorage buffer that
// flushes on reconnect. Real reconciliation (dedupe-on-flush, cross-device
// merge) is S8 — not here.
import { capture as apiCapture, type CaptureBody } from "@gulp/api-client";
import { logError } from "./logger";

export type PendingCapture = {
  localId: string;
  url?: string;
  text?: string;
  note?: string;
  title?: string;
  tags: string[];
  captured_via: "paste" | "in_app" | "manual";
};

const KEY = "gulp.captureQueue";

export function readQueue(): PendingCapture[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as PendingCapture[];
  } catch (err) {
    logError("capture queue read failed", err);
    return [];
  }
}

function writeQueue(q: PendingCapture[]): void {
  localStorage.setItem(KEY, JSON.stringify(q));
}

export function enqueuePending(item: PendingCapture): void {
  writeQueue([...readQueue(), item]);
}

type Sender = (body: CaptureBody) => Promise<unknown>;

export async function flushQueue(send: Sender = apiCapture): Promise<number> {
  const queue = readQueue();
  const remaining: PendingCapture[] = [];
  let flushed = 0;
  for (const item of queue) {
    try {
      await send({
        url: item.url,
        text: item.text,
        note: item.note,
        title: item.title,
        tags: item.tags,
        captured_via: item.captured_via,
      });
      flushed += 1;
    } catch (err) {
      logError("capture queue flush failed", err, { localId: item.localId });
      remaining.push(item);
    }
  }
  writeQueue(remaining);
  return flushed;
}
