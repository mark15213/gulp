import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  cookies: vi.fn(),
  getFeedEntries: vi.fn(),
  getSubscriptions: vi.fn(),
}));

vi.mock("next/headers", () => ({ cookies: mocks.cookies }));
vi.mock("@gulp/api-client", () => ({
  getCurrentGulpSession: vi.fn(),
  getFeedEntries: mocks.getFeedEntries,
  getInbox: vi.fn(),
  getLibrary: vi.fn(),
  getMe: vi.fn(),
  getPack: vi.fn(),
  getSnapshot: vi.fn(),
  getSubscriptions: mocks.getSubscriptions,
  getToday: vi.fn(),
}));

import { getFeedEntries, getSubscriptions } from "./serverApi";

describe("server API authentication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.cookies.mockResolvedValue({
      toString: () => "gulp_session=session-token",
    });
  });

  it("passes the current request cookie to a server API call", async () => {
    await getSubscriptions();

    expect(mocks.getSubscriptions).toHaveBeenCalledWith({
      headers: { cookie: "gulp_session=session-token" },
    });
  });

  it("passes the current request cookie alongside helper arguments", async () => {
    await getFeedEntries();

    expect(mocks.getFeedEntries).toHaveBeenCalledWith(undefined, {
      headers: { cookie: "gulp_session=session-token" },
    });
  });
});
