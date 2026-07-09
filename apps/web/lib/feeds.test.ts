import { describe, expect, it } from "vitest";
import { sanitizeFeedHtml } from "./feeds";

describe("sanitizeFeedHtml", () => {
  it("strips scripts, iframes, and inline handlers", () => {
    const dirty =
      '<p onclick="evil()">hi</p><script>evil()</script><iframe src="x"></iframe><b>ok</b>';
    expect(sanitizeFeedHtml(dirty)).toBe("<p>hi</p><b>ok</b>");
  });

  it("keeps ordinary markup", () => {
    const clean = '<p>Hello <a href="https://a">link</a> <img src="https://i"/></p>';
    expect(sanitizeFeedHtml(clean)).toBe(clean);
  });
});
