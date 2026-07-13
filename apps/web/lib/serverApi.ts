import "server-only";

import { cookies } from "next/headers";
import {
  getCurrentGulpSession as getCurrentGulpSessionFromApi,
  getFeedEntries as getFeedEntriesFromApi,
  getInbox as getInboxFromApi,
  getLibrary as getLibraryFromApi,
  getMe as getMeFromApi,
  getPack as getPackFromApi,
  getSnapshot as getSnapshotFromApi,
  getSubscriptions as getSubscriptionsFromApi,
  getToday as getTodayFromApi,
} from "@gulp/api-client";

async function authenticatedRequest() {
  return { headers: { cookie: (await cookies()).toString() } };
}

export async function getMe() {
  return getMeFromApi(await authenticatedRequest());
}

export async function getToday() {
  return getTodayFromApi(await authenticatedRequest());
}

export async function getCurrentGulpSession() {
  return getCurrentGulpSessionFromApi(await authenticatedRequest());
}

export async function getInbox() {
  return getInboxFromApi(await authenticatedRequest());
}

export async function getLibrary() {
  return getLibraryFromApi(await authenticatedRequest());
}

export async function getSubscriptions() {
  return getSubscriptionsFromApi(await authenticatedRequest());
}

export async function getFeedEntries() {
  return getFeedEntriesFromApi(undefined, await authenticatedRequest());
}

export async function getSnapshot(id: string) {
  return getSnapshotFromApi(id, await authenticatedRequest());
}

export async function getPack(id: string) {
  return getPackFromApi(id, await authenticatedRequest());
}
