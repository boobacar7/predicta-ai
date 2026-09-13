import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Minimal image for infra/containers/compose.staging.yml (node server.js).
  output: "standalone",
  /**
   * AI Picks and Value Finder moved to `/ai-picks` and `/value-finder`, the
   * paths used by the product navigation. The previous prototype paths keep
   * working so bookmarks and any fixture linking to them do not break.
   */
  async redirects() {
    return [
      { source: "/picks", destination: "/ai-picks", permanent: true },
      { source: "/value", destination: "/value-finder", permanent: true },
    ];
  },
};

export default nextConfig;
