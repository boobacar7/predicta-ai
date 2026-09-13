import type { NextConfig } from "next";
import { LEGACY_FOOTBALL_REDIRECTS } from "./src/lib/football/routes";

const nextConfig: NextConfig = {
  // Minimal image for infra/containers/compose.staging.yml (node server.js).
  output: "standalone",
  /**
   * P1 product lives at `/football/*`. Previous prototype paths redirect so
   * bookmarks and in-app leftovers do not 404.
   */
  async redirects() {
    return [...LEGACY_FOOTBALL_REDIRECTS];
  },
};

export default nextConfig;
