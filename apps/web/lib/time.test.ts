import { describe, expect, it } from "vitest";
import { timeAgo } from "./time";

const now = new Date("2026-07-02T12:00:00Z");

describe("timeAgo", () => {
  it("buckets seconds/minutes/hours/days", () => {
    expect(timeAgo("2026-07-02T11:59:30Z", now)).toBe("just now");
    expect(timeAgo("2026-07-02T11:48:00Z", now)).toBe("12m ago");
    expect(timeAgo("2026-07-02T09:00:00Z", now)).toBe("3h ago");
    expect(timeAgo("2026-07-01T09:00:00Z", now)).toBe("yesterday");
    expect(timeAgo("2026-06-29T09:00:00Z", now)).toBe("3d ago");
  });

  it("falls back to a short date beyond a week", () => {
    expect(timeAgo("2026-06-10T09:00:00Z", now)).toBe("Jun 10");
  });

  it("treats naive timestamps as UTC", () => {
    expect(timeAgo("2026-07-02T11:48:00", now)).toBe("12m ago");
  });

  it("clamps future skew to just now", () => {
    expect(timeAgo("2026-07-02T12:00:05Z", now)).toBe("just now");
  });
});
