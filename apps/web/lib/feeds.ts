// Feed-entry HTML hygiene: feed content is third-party markup rendered via
// dangerouslySetInnerHTML in the reader pane. Strip active content; a full
// allowlist sanitizer is a fast-follow (spec 2026-07-09 §5).
export function sanitizeFeedHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, "")
    .replace(/\son\w+\s*=\s*"[^"]*"/gi, "")
    .replace(/\son\w+\s*=\s*'[^']*'/gi, "");
}
