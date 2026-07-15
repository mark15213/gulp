import type { NextConfig } from "next";

const API =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

const nextConfig: NextConfig = {
  // Self-contained server build for the container runtime image (infra/Dockerfile.web).
  output: "standalone",
  // Allow importing source (incl. tokens.css) from the workspace design system.
  transpilePackages: ["@gulp/ui"],
  async rewrites() {
    // Browser hits /api/* same-origin (first-party session cookie); Next proxies
    // to the FastAPI service. Also resolves prod cross-origin (Vercel ↔ Railway).
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
};

export default nextConfig;
