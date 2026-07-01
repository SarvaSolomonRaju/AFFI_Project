import { defineConfig } from "@playwright/test";

// Runs against the real dev server with the real backend — this is
// deliberately not mocked, unlike the Vitest component tests. It's the
// one test that actually exercises FloodMap (MapLibre needs real
// WebGL, which jsdom doesn't have).
export default defineConfig({
  testDir: "./e2e",
  use: {
    baseURL: "http://localhost:5173",
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
  },
});
