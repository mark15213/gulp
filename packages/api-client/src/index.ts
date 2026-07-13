// The single contract surface between the Python API and the TS clients.
// `just gen-client` writes ./schema.gen.ts from the API's OpenAPI; the typed
// helpers below are the only thing apps import.
import createClient from "openapi-fetch";
import type { paths } from "./schema.gen";

// Browser: same-origin "/api" (proxied by the Next rewrite) so the httpOnly
// session cookie is first-party. Server (SSR): absolute API URL — apps/web
// forwards the incoming cookie via openapi-fetch middleware (see web layout).
export const baseUrl =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_URL ??
      process.env.NEXT_PUBLIC_API_URL ??
      "http://localhost:8000"
    : "/api";

export const client = createClient<paths>({ baseUrl, credentials: "include" });

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

export type SnapshotPatchBody =
  paths["/snapshots/{snapshot_id}"]["patch"]["requestBody"]["content"]["application/json"];
export type SourceGenre = SnapshotPatchBody["genre"];

// Curation-time corrections (currently: genre). Re-run processing afterwards
// for the new genre's strategy to take effect.
export async function updateSnapshot(
  id: string,
  patch: SnapshotPatchBody,
): Promise<SnapshotOut> {
  const { data, error } = await client.PATCH("/snapshots/{snapshot_id}", {
    params: { path: { snapshot_id: id } },
    body: patch,
  });
  if (error || !data) throw new Error("snapshot update failed");
  return data;
}

// Cascade soft-delete: removes the snapshot and all its derivatives (pack, cards, …).
export async function deleteSnapshot(id: string): Promise<void> {
  const { error } = await client.DELETE("/snapshots/{snapshot_id}", {
    params: { path: { snapshot_id: id } },
  });
  if (error) throw new Error("delete snapshot failed");
}

// User tags on a snapshot (the Library's "Mine" facet). Add is idempotent;
// remove soft-deletes. Both return the updated snapshot.
export async function addSnapshotTag(id: string, tag: string): Promise<SnapshotOut> {
  const { data, error } = await client.POST("/snapshots/{snapshot_id}/tags", {
    params: { path: { snapshot_id: id } },
    body: { tag },
  });
  if (error || !data) throw new Error("add tag failed");
  return data;
}

export async function removeSnapshotTag(id: string, tag: string): Promise<SnapshotOut> {
  const { data, error } = await client.DELETE("/snapshots/{snapshot_id}/tags", {
    params: { path: { snapshot_id: id }, query: { tag } },
  });
  if (error || !data) throw new Error("remove tag failed");
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
  const res = await fetch(`${baseUrl}/snapshots/${id}/import`, {
    method: "POST",
    body,
    credentials: "include",
  });
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
  const res = await fetch(cardsJobDownloadUrl(snapshotId), {
    method: "HEAD",
    credentials: "include",
  });
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
  paths["/snapshots/{snapshot_id}/messages"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type MessageCreateBody =
  paths["/snapshots/{snapshot_id}/messages"]["post"]["requestBody"]["content"]["application/json"];

export async function getPackMessages(snapshotId: string): Promise<MessageOut[]> {
  const { data, error } = await client.GET("/snapshots/{snapshot_id}/messages", {
    params: { path: { snapshot_id: snapshotId } },
    cache: "no-store",
  });
  if (error || !data) throw new Error("fetch messages failed");
  return data;
}

export async function postPackMessage(
  snapshotId: string,
  body: MessageCreateBody,
): Promise<MessageOut> {
  const { data, error } = await client.POST("/snapshots/{snapshot_id}/messages", {
    params: { path: { snapshot_id: snapshotId } },
    body,
  });
  if (error || !data) throw new Error("post message failed");
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

export type GulpSession =
  paths["/gulp/sessions"]["post"]["responses"]["200"]["content"]["application/json"];
export type SessionCard = GulpSession["cards"][number];
export type ReviewResult =
  paths["/gulp/sessions/{session_id}/reviews"]["post"]["responses"]["200"]["content"]["application/json"];
export type GulpSummary =
  paths["/gulp/sessions/{session_id}/complete"]["post"]["responses"]["200"]["content"]["application/json"];

export async function startGulpSession(
  body: { scope_type?: "daily" | "at_risk" | "free_explore"; target_minutes?: number } = {},
): Promise<GulpSession> {
  // schema.gen.ts marks `scope_type` non-optional because it carries a Pydantic
  // default (openapi-typescript's defaultNonNullable) — mirror that default here
  // so callers can still omit it.
  const { data, error } = await client.POST("/gulp/sessions", {
    body: { scope_type: body.scope_type ?? "daily", target_minutes: body.target_minutes },
  });
  if (error || !data) throw new Error("start gulp failed");
  return data;
}

export async function getCurrentGulpSession(): Promise<GulpSession | null> {
  const { data, error } = await client.GET("/gulp/sessions/current", { cache: "no-store" });
  if (error) throw new Error("current session fetch failed");
  return data ?? null;
}

export async function getGulpSession(id: string): Promise<GulpSession> {
  const { data, error } = await client.GET("/gulp/sessions/{session_id}", {
    params: { path: { session_id: id } }, cache: "no-store",
  });
  if (error || !data) throw new Error("session fetch failed");
  return data;
}

export async function reviewCard(
  sessionId: string,
  body: { card_id: string; grade: "got_it" | "fuzzy" | "missed"; response?: string | null },
): Promise<ReviewResult> {
  const { data, error } = await client.POST("/gulp/sessions/{session_id}/reviews", {
    params: { path: { session_id: sessionId } }, body,
  });
  if (error || !data) throw new Error("review failed");
  return data;
}

export async function snoozeCard(sessionId: string, cardId: string): Promise<ReviewResult> {
  const { data, error } = await client.POST("/gulp/sessions/{session_id}/snooze", {
    params: { path: { session_id: sessionId } }, body: { card_id: cardId },
  });
  if (error || !data) throw new Error("snooze failed");
  return data;
}

export async function completeGulpSession(sessionId: string): Promise<GulpSummary> {
  const { data, error } = await client.POST("/gulp/sessions/{session_id}/complete", {
    params: { path: { session_id: sessionId } },
  });
  if (error || !data) throw new Error("complete failed");
  return data;
}

// ── Feeds (spec 2026-07-09) ─────────────────────────────────────────────────

export type SubscriptionsOut =
  paths["/subscriptions"]["get"]["responses"]["200"]["content"]["application/json"];
export type Subscription = SubscriptionsOut["items"][number];
export type SubscriptionCreateResponse =
  paths["/subscriptions"]["post"]["responses"]["200"]["content"]["application/json"];
export type FeedEntriesOut =
  paths["/feed-entries"]["get"]["responses"]["200"]["content"]["application/json"];
export type FeedEntry = FeedEntriesOut["items"][number];
export type CatalogSearchOut =
  paths["/feeds/catalog/search"]["get"]["responses"]["200"]["content"]["application/json"];
export type CatalogRoute = CatalogSearchOut["items"][number];

export async function getSubscriptions(): Promise<SubscriptionsOut> {
  const { data, error } = await client.GET("/subscriptions", { cache: "no-store" });
  if (error || !data) throw new Error("subscriptions fetch failed");
  return data;
}

export async function createSubscription(body: {
  feed_url: string;
  title?: string | null;
}): Promise<SubscriptionCreateResponse> {
  const { data, error } = await client.POST("/subscriptions", { body });
  if (error || !data) throw new Error("subscription create failed");
  return data;
}

export async function patchSubscription(
  id: string,
  body: { title?: string | null; muted?: boolean | null },
): Promise<Subscription> {
  const { data, error } = await client.PATCH("/subscriptions/{sub_id}", {
    params: { path: { sub_id: id } },
    body,
  });
  if (error || !data) throw new Error("subscription update failed");
  return data;
}

export async function deleteSubscription(id: string): Promise<void> {
  const { error } = await client.DELETE("/subscriptions/{sub_id}", {
    params: { path: { sub_id: id } },
  });
  if (error) throw new Error("subscription delete failed");
}

export async function refreshSubscription(id: string): Promise<void> {
  const { error } = await client.POST("/subscriptions/{sub_id}/refresh", {
    params: { path: { sub_id: id } },
  });
  if (error) throw new Error("subscription refresh failed");
}

export async function readAllSubscription(id: string): Promise<void> {
  const { error } = await client.POST("/subscriptions/{sub_id}/read-all", {
    params: { path: { sub_id: id } },
  });
  if (error) throw new Error("read-all failed");
}

export async function getFeedEntries(params?: {
  subscriptionId?: string;
  unreadOnly?: boolean;
  limit?: number;
  offset?: number;
}): Promise<FeedEntriesOut> {
  const query = {
    unread_only: params?.unreadOnly,
    limit: params?.limit,
    offset: params?.offset,
  };
  if (params?.subscriptionId) {
    const { data, error } = await client.GET("/subscriptions/{sub_id}/entries", {
      params: { path: { sub_id: params.subscriptionId }, query },
      cache: "no-store",
    });
    if (error || !data) throw new Error("entries fetch failed");
    return data;
  }
  const { data, error } = await client.GET("/feed-entries", {
    params: { query },
    cache: "no-store",
  });
  if (error || !data) throw new Error("entries fetch failed");
  return data;
}

export async function setEntryRead(id: string, read: boolean): Promise<void> {
  if (read) {
    const { error } = await client.POST("/feed-entries/{entry_id}/read", {
      params: { path: { entry_id: id } },
    });
    if (error) throw new Error("read toggle failed");
    return;
  }
  const { error } = await client.POST("/feed-entries/{entry_id}/unread", {
    params: { path: { entry_id: id } },
  });
  if (error) throw new Error("read toggle failed");
}

export async function gulpEntry(
  id: string,
): Promise<
  paths["/feed-entries/{entry_id}/gulp"]["post"]["responses"]["200"]["content"]["application/json"]
> {
  const { data, error } = await client.POST("/feed-entries/{entry_id}/gulp", {
    params: { path: { entry_id: id } },
  });
  if (error || !data) throw new Error("gulp failed");
  return data;
}

export async function searchCatalog(q: string, limit = 30): Promise<CatalogSearchOut> {
  const { data, error } = await client.GET("/feeds/catalog/search", {
    params: { query: { q, limit } },
  });
  if (error || !data) throw new Error("catalog search failed");
  return data;
}

// ── Auth (spec 2026-07-10) ──────────────────────────────────────────────────

export type UserPublic =
  paths["/auth/me"]["get"]["responses"]["200"]["content"]["application/json"];
export type RegisterBody =
  paths["/auth/register"]["post"]["requestBody"]["content"]["application/json"];
export type LoginBody =
  paths["/auth/login"]["post"]["requestBody"]["content"]["application/json"];

export async function register(body: RegisterBody): Promise<UserPublic> {
  const { data, error } = await client.POST("/auth/register", { body });
  if (error || !data) throw new Error("register failed");
  return data;
}

export async function login(body: LoginBody): Promise<UserPublic> {
  const { data, error } = await client.POST("/auth/login", { body });
  if (error || !data) throw new Error("login failed");
  return data;
}

export async function logout(): Promise<void> {
  await client.POST("/auth/logout", {});
}

/** Current user, or null if unauthenticated (401). */
export async function getMe(): Promise<UserPublic | null> {
  const { data, error } = await client.GET("/auth/me", { cache: "no-store" });
  if (error || !data) return null;
  return data;
}

export * from "./llm";
