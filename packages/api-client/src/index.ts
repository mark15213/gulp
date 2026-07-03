// The single contract surface between the Python API and the TS clients.
// `just gen-client` writes ./schema.gen.ts from the API's OpenAPI; the typed
// helpers below are the only thing apps import.
import createClient from "openapi-fetch";
import type { paths } from "./schema.gen";

export const baseUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const client = createClient<paths>({ baseUrl });

export type CaptureBody =
  paths["/capture"]["post"]["requestBody"]["content"]["application/json"];
export type CaptureResponse =
  paths["/capture"]["post"]["responses"]["200"]["content"]["application/json"];
export type InboxOut =
  paths["/inbox"]["get"]["responses"]["200"]["content"]["application/json"];
export type Snapshot = InboxOut["items"][number];
export type SnapshotOut =
  paths["/snapshots/{snapshot_id}"]["get"]["responses"]["200"]["content"]["application/json"];
export type PackOut =
  paths["/snapshots/{snapshot_id}/pack"]["get"]["responses"]["200"]["content"]["application/json"];

export async function capture(body: CaptureBody): Promise<CaptureResponse> {
  const { data, error } = await client.POST("/capture", { body });
  if (error || !data) throw new Error("capture failed");
  return data;
}

export async function getInbox(): Promise<InboxOut> {
  const { data, error } = await client.GET("/inbox", { cache: "no-store" });
  if (error || !data) throw new Error("inbox fetch failed");
  return data;
}

export type LibraryOut =
  paths["/library"]["get"]["responses"]["200"]["content"]["application/json"];

export async function getLibrary(): Promise<LibraryOut> {
  const { data, error } = await client.GET("/library", { cache: "no-store" });
  if (error || !data) throw new Error("library fetch failed");
  return data;
}

export type TodayOut =
  paths["/today"]["get"]["responses"]["200"]["content"]["application/json"];

export async function getToday(): Promise<TodayOut> {
  const { data, error } = await client.GET("/today", { cache: "no-store" });
  if (error || !data) throw new Error("today fetch failed");
  return data;
}

export async function getSnapshot(id: string): Promise<Snapshot> {
  const { data, error } = await client.GET("/snapshots/{snapshot_id}", {
    params: { path: { snapshot_id: id } },
    cache: "no-store",
  });
  if (error || !data) throw new Error("snapshot fetch failed");
  return data;
}

// v1 limitation: ALL error responses (404, 5xx, network) collapse to `null`.
// This is fine while "no pack yet" is the only expected error state.
// Plan B must distinguish a real 404 from a 5xx/4xx before shipping production
// error handling (e.g. surface retries on 5xx, show a permanent error on 4xx).
export async function getPack(id: string): Promise<PackOut | null> {
  const { data, error } = await client.GET("/snapshots/{snapshot_id}/pack", {
    params: { path: { snapshot_id: id } },
    cache: "no-store",
  });
  if (error) return null; // 404 = no pack yet (still processing / needs attention)
  return data ?? null;
}

export async function startProcessing(id: string): Promise<SnapshotOut> {
  const { data, error } = await client.POST("/snapshots/{snapshot_id}/process", {
    params: { path: { snapshot_id: id } },
  });
  if (error || !data) throw new Error("start processing failed");
  return data;
}

export async function startExport(id: string): Promise<SnapshotOut> {
  const { data, error } = await client.POST("/snapshots/{snapshot_id}/export", {
    params: { path: { snapshot_id: id } },
  });
  if (error || !data) throw new Error("export failed");
  return data;
}

export function jobDownloadUrl(id: string): string {
  return `${baseUrl}/snapshots/${id}/job`;
}

export async function importResult(id: string, file: File): Promise<SnapshotOut> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${baseUrl}/snapshots/${id}/import`, { method: "POST", body });
  if (!res.ok) throw new Error(`import failed (${res.status})`);
  return (await res.json()) as SnapshotOut;
}

export type PackBlockOut = PackOut["sections"][number]["blocks"][number];
export type BlockUpdateBody =
  paths["/snapshots/{snapshot_id}/blocks/{block_id}"]["patch"]["requestBody"]["content"]["application/json"];
export type BlockCreateBody =
  paths["/snapshots/{snapshot_id}/sections/{section_id}/blocks"]["post"]["requestBody"]["content"]["application/json"];

export async function updateBlock(
  snapshotId: string,
  blockId: string,
  body: BlockUpdateBody,
): Promise<PackBlockOut> {
  const { data, error } = await client.PATCH("/snapshots/{snapshot_id}/blocks/{block_id}", {
    params: { path: { snapshot_id: snapshotId, block_id: blockId } },
    body,
  });
  if (error || !data) throw new Error("update block failed");
  return data;
}

export async function createBlock(
  snapshotId: string,
  sectionId: string,
  body: BlockCreateBody,
): Promise<PackBlockOut> {
  const { data, error } = await client.POST(
    "/snapshots/{snapshot_id}/sections/{section_id}/blocks",
    { params: { path: { snapshot_id: snapshotId, section_id: sectionId } }, body },
  );
  if (error || !data) throw new Error("create block failed");
  return data;
}

export async function deleteBlock(snapshotId: string, blockId: string): Promise<void> {
  const { error } = await client.DELETE("/snapshots/{snapshot_id}/blocks/{block_id}", {
    params: { path: { snapshot_id: snapshotId, block_id: blockId } },
  });
  if (error) throw new Error("delete block failed");
}

export type CardOut =
  paths["/snapshots/{snapshot_id}/cards"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type CardsImportBody =
  paths["/snapshots/{snapshot_id}/cards/import"]["post"]["requestBody"]["content"]["application/json"];
export type CardPatchBody =
  paths["/snapshots/{snapshot_id}/cards/{card_id}"]["patch"]["requestBody"]["content"]["application/json"];

export async function getCards(snapshotId: string): Promise<CardOut[]> {
  const { data, error } = await client.GET("/snapshots/{snapshot_id}/cards", {
    params: { path: { snapshot_id: snapshotId } },
    cache: "no-store",
  });
  if (error || !data) throw new Error("fetch cards failed");
  return data;
}

export async function generateCards(snapshotId: string): Promise<SnapshotOut> {
  const { data, error } = await client.POST("/snapshots/{snapshot_id}/cards/generate", {
    params: { path: { snapshot_id: snapshotId } },
  });
  if (error || !data) throw new Error("generate cards failed");
  return data;
}

// Package the card-generation job as a zip to run in Claude Code / Codex, then
// import the produced cards.json back through the normal "Import cards" flow.
export async function exportCardsJob(snapshotId: string): Promise<SnapshotOut> {
  const { data, error } = await client.POST("/snapshots/{snapshot_id}/cards/export", {
    params: { path: { snapshot_id: snapshotId } },
  });
  if (error || !data) throw new Error("export cards job failed");
  return data;
}

export function cardsJobDownloadUrl(snapshotId: string): string {
  return `${baseUrl}/snapshots/${snapshotId}/cards/job`;
}

/** True once the worker has finished building the zip (GET 200 vs 404). */
export async function cardsJobReady(snapshotId: string): Promise<boolean> {
  const res = await fetch(cardsJobDownloadUrl(snapshotId), { method: "HEAD" });
  return res.ok;
}

/** Pull the built cards job to the user's machine without navigating away. */
export function downloadCardsJob(snapshotId: string): void {
  const a = document.createElement("a");
  a.href = cardsJobDownloadUrl(snapshotId); // server sends Content-Disposition: attachment
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export async function importCards(
  snapshotId: string,
  body: CardsImportBody,
): Promise<CardOut[]> {
  const { data, error, response } = await client.POST(
    "/snapshots/{snapshot_id}/cards/import",
    { params: { path: { snapshot_id: snapshotId } }, body },
  );
  if (error || !data) {
    // 422 carries field-level validation errors worth surfacing verbatim.
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    throw new Error(
      detail ? `import cards failed: ${JSON.stringify(detail)}` : `import cards failed (${response?.status})`,
    );
  }
  return data;
}

export async function updateCard(
  snapshotId: string,
  cardId: string,
  body: CardPatchBody,
): Promise<CardOut> {
  const { data, error } = await client.PATCH("/snapshots/{snapshot_id}/cards/{card_id}", {
    params: { path: { snapshot_id: snapshotId, card_id: cardId } },
    body,
  });
  if (error || !data) throw new Error("update card failed");
  return data;
}

export async function deleteCard(snapshotId: string, cardId: string): Promise<void> {
  const { error } = await client.DELETE("/snapshots/{snapshot_id}/cards/{card_id}", {
    params: { path: { snapshot_id: snapshotId, card_id: cardId } },
  });
  if (error) throw new Error("delete card failed");
}

export type MessageOut =
  paths["/snapshots/{snapshot_id}/blocks/{block_id}/messages"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type MessageCreateBody =
  paths["/snapshots/{snapshot_id}/blocks/{block_id}/messages"]["post"]["requestBody"]["content"]["application/json"];

export async function getBlockMessages(
  snapshotId: string,
  blockId: string,
): Promise<MessageOut[]> {
  const { data, error } = await client.GET(
    "/snapshots/{snapshot_id}/blocks/{block_id}/messages",
    { params: { path: { snapshot_id: snapshotId, block_id: blockId } }, cache: "no-store" },
  );
  if (error || !data) throw new Error("fetch block messages failed");
  return data;
}

export async function postBlockMessage(
  snapshotId: string,
  blockId: string,
  body: MessageCreateBody,
): Promise<MessageOut> {
  const { data, error } = await client.POST(
    "/snapshots/{snapshot_id}/blocks/{block_id}/messages",
    { params: { path: { snapshot_id: snapshotId, block_id: blockId } }, body },
  );
  if (error || !data) throw new Error("post block message failed");
  return data;
}

export type FigureAssetOut =
  paths["/snapshots/{snapshot_id}/figures"]["get"]["responses"]["200"]["content"]["application/json"][number];

export async function getFigures(snapshotId: string): Promise<FigureAssetOut[]> {
  const { data, error } = await client.GET("/snapshots/{snapshot_id}/figures", {
    params: { path: { snapshot_id: snapshotId } },
    cache: "no-store",
  });
  if (error || !data) throw new Error("figures fetch failed");
  return data;
}

// Bytes URL for an <img src>. Built from baseUrl like the other non-JSON endpoints.
export function figureUrl(snapshotId: string, figureId: string): string {
  return `${baseUrl}/snapshots/${snapshotId}/figures/${figureId}`;
}
