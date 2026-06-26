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
