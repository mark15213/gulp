import type { NextConfig } from "next";

// The /api/* rewrite destination is baked at BUILD time. Read the backend URL
// from the environment; tolerate a missing scheme and a trailing slash.
let API = (process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "").trim();
if (API && !/^https?:\/\//i.test(API)) API = `https://${API}`;
API = API.replace(/\/+$/, "");

// On a Vercel production build a missing value would silently fall back to
// localhost, and the proxied /api calls then fail at runtime with
// DNS_HOSTNAME_RESOLVED_PRIVATE. Fail the build loudly instead so the misconfig
// is obvious rather than cryptic.
if (!API && process.env.VERCEL_ENV === "production") {
  throw new Error(
    "API_INTERNAL_URL is not set at build time. Set it to the Railway public URL " +
      "(https://<app>.up.railway.app) in the Vercel project's Production environment and rebuild.",
  );
}

const apiBase = API || "http://localhost:8000";

const nextConfig: NextConfig = {
  // Allow importing source (incl. tokens.css) from the workspace design system.
  transpilePackages: ["@gulp/ui"],
  async rewrites() {
    // Browser hits /api/* same-origin (first-party session cookie); Next proxies
    // to the FastAPI service (Railway in prod).
    return [{ source: "/api/:path*", destination: `${apiBase}/:path*` }];
  },
};

export default nextConfig;
