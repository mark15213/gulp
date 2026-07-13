// Streaming reader chat (spec 2026-07-13 §5.2). SSE is outside the OpenAPI
// surface; this thin parser is hand-rolled on purpose.
import { baseUrl, type MessageOut } from "./index";

export type ChatStreamEvent =
  | { type: "delta"; text: string }
  | { type: "done"; message: MessageOut }
  | { type: "error"; code: string };

export async function* streamPackMessage(
  snapshotId: string,
  body: { content: string; block_refs: string[] },
): AsyncGenerator<ChatStreamEvent> {
  const res = await fetch(`${baseUrl}/snapshots/${snapshotId}/messages/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error("chat stream failed");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (line) yield JSON.parse(line.slice(6)) as ChatStreamEvent;
    }
  }
}
