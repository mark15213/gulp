import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow importing source (incl. tokens.css) from the workspace design system.
  transpilePackages: ["@gulp/ui"],
};

export default nextConfig;
