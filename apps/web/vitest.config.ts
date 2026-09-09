import tsconfigPaths from "vite-tsconfig-paths";
import { defineConfig } from "vitest/config";

/**
 * JSX is transformed by esbuild using the `react-jsx` runtime from tsconfig.
 * `@vitejs/plugin-react` is intentionally absent: its only extra feature here
 * would be Fast Refresh, which tests do not use, and it pulls in a second major
 * version of Vite alongside the one Vitest ships.
 */
export default defineConfig({
  plugins: [tsconfigPaths()],
  esbuild: { jsx: "automatic" },
  test: {
    environment: "jsdom",
    // Test helpers are imported explicitly, so no ambient globals are declared.
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
