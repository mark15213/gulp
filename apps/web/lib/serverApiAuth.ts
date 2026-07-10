import "server-only";
import { cookies } from "next/headers";
import { client } from "@gulp/api-client";

// Server Components render on the Node side, where fetch has no cookie jar.
// Attach the incoming request's cookies to every api-client call so SSR data
// fetches are authenticated. This module only loads in the server bundle
// ("server-only"), so it never runs in the browser client instance.
let registered = false;

export function ensureServerApiAuth(): void {
  if (registered) return;
  registered = true;
  client.use({
    async onRequest({ request }) {
      const cookieHeader = (await cookies()).toString();
      if (cookieHeader) request.headers.set("cookie", cookieHeader);
      return request;
    },
  });
}
