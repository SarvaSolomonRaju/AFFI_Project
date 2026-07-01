import { test, expect } from "@playwright/test";

// One end-to-end smoke test: load the real app against the real
// backend and confirm the whole thing renders — alert banner, map,
// slider, forecast table. This requires `make serve-api` to be
// running (AFFI_AUTH_DISABLED=true) separately; it is not started by
// this test.
test("full page loads with live data from the backend", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /FloodAI/ })).toBeVisible();

  // Alert banner: real data, not the loading placeholder
  await expect(page.getByText(/Current alert:/)).toBeVisible({ timeout: 10_000 });

  // Map: MapLibre draws to a <canvas>, so we just confirm it mounted
  await expect(page.locator("canvas.maplibregl-canvas")).toBeVisible({ timeout: 10_000 });

  // Simulation slider defaults to the 100-yr scenario
  await expect(page.getByText(/100-year storm/)).toBeVisible({ timeout: 10_000 });

  // Action plan: real named roads/buildings, not placeholders
  await expect(page.getByText(/Roads to barricade/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/28-910/)).toBeVisible();

  // Forecast table has at least one real date row
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(7);
});
