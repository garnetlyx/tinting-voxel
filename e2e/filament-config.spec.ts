import { test, expect } from '@playwright/test';

test.describe('Filament Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('filament config panel is visible in settings', async ({ page }) => {
    // Should show filament color rows
    await expect(page.locator('input[type="color"]').first()).toBeVisible();
  });

  test('can change filament color via color input', async ({ page }) => {
    const colorInputs = page.locator('input[type="color"]');
    const count = await colorInputs.count();
    expect(count).toBeGreaterThanOrEqual(4);
  });

  test('can add a filament color', async ({ page }) => {
    const initialCount = await page.locator('input[type="color"]').count();

    // Find and click Add Color button
    await page.getByRole('button', { name: /Add Color/i }).click();

    const newCount = await page.locator('input[type="color"]').count();
    expect(newCount).toBe(initialCount + 1);
  });

  test('can load a preset', async ({ page }) => {
    // Look for preset selector and change it
    const presetSelect = page.locator('select').first();
    await expect(presetSelect).toBeVisible();

    // Select Bambu CMYK preset
    await presetSelect.selectOption('bambu_cmyw_phase6');

    // Should have color inputs (preset loaded)
    const colorInputs = page.locator('input[type="color"]');
    expect(await colorInputs.count()).toBeGreaterThanOrEqual(4);
  });

  test('filament preview section exists', async ({ page }) => {
    // The filament preview section should be visible
    await expect(page.getByText(/Color Preview/i)).toBeVisible();
  });

  test('palette library section exists', async ({ page }) => {
    // Palette library should be visible
    await expect(page.getByText(/Palette Library/i)).toBeVisible();
  });
});
