import { describe, expect, it } from "vitest";
import type { FeedEntry, Snapshot } from "@gulp/api-client";
import { STAGES, isActionable, stageOf, triageOf } from "./stages";

const entry = (over: Partial<FeedEntry> = {}): FeedEntry =>
  ({
    id: "e1",
    subscription_id: "sub1",
    subscription_title: "少数派",
    title: "An entry",
    url: "https://example.com/1",
    author: null,
    published_at: null,
    content_html: null,
    read: false,
    skipped: false,
    promoted_source_id: null,
    created_at: "2026-08-01T00:00:00Z",
    ...over,
  }) as FeedEntry;

describe("stage assignment", () => {
  it("orders the belt New → Kept → Needs you → In flight", () => {
    expect(STAGES.map((s) => s.key)).toEqual(["new", "kept", "needs", "flight"]);
  });

  it("puts each status in exactly one section", () => {
    expect(stageOf("unprocessed")).toBe("kept");
    expect(stageOf("exported")).toBe("needs");
    expect(stageOf("needs_attention")).toBe("needs");
    expect(stageOf("queued")).toBe("flight");
    expect(stageOf("processing")).toBe("flight");
  });

  it("keeps `ready` off the surface — it has left for the Library", () => {
    expect(stageOf("ready")).toBeNull();
  });
});

describe("actionable (the badge)", () => {
  it("counts what waits on you", () => {
    expect(["unprocessed", "exported", "needs_attention"].every(
      (s) => isActionable(s as Snapshot["status"]),
    )).toBe(true);
  });

  it("never counts the machine's own work", () => {
    expect(isActionable("queued")).toBe(false);
    expect(isActionable("processing")).toBe(false);
    expect(isActionable("ready")).toBe(false);
  });
});

describe("triage", () => {
  it("treats a seen-but-undecided entry as pending", () => {
    expect(triageOf(entry({ read: true }))).toBe("pending");
  });

  it("reads skipped and forwarded off their own fields", () => {
    expect(triageOf(entry({ skipped: true }))).toBe("skipped");
    expect(triageOf(entry({ promoted_source_id: "s1" }))).toBe("forwarded");
  });

  it("lets forwarded win over a stale skip", () => {
    expect(triageOf(entry({ skipped: true, promoted_source_id: "s1" }))).toBe("forwarded");
  });
});
