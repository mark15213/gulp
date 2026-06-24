import { beforeEach, describe, expect, it } from "vitest";
import type { CaptureBody } from "@gulp/api-client";
import { enqueuePending, flushQueue, readQueue } from "./captureQueue";

beforeEach(() => localStorage.clear());

describe("captureQueue", () => {
  it("persists and reads pending captures", () => {
    enqueuePending({ localId: "1", url: "https://a.com", tags: [], captured_via: "paste" });
    expect(readQueue()).toHaveLength(1);
  });

  it("flushes successes and keeps failures", async () => {
    enqueuePending({ localId: "1", url: "https://a.com", tags: [], captured_via: "paste" });
    enqueuePending({ localId: "2", url: "https://b.com", tags: [], captured_via: "paste" });

    const send = async (body: CaptureBody) => {
      if (body.url?.includes("b.com")) throw new Error("offline");
      return {} as never;
    };

    const flushed = await flushQueue(send);
    expect(flushed).toBe(1);
    expect(readQueue()).toHaveLength(1);
    expect(readQueue()[0]?.url).toContain("b.com");
  });
});
