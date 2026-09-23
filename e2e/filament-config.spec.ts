import { test, expect } from '@playwright/test';

test.describe('Filament Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // The converter stays inert until the material catalog has loaded.
    await expect(page.locator('input[type="color"]').first()).toBeVisible();
  });

  test('filament config panel is visible in settings', async ({ page }) => {
    await expect(page.getByRole('combobox', { name: 'Filament Preset' })).toBeVisible();
  });

  test('default preset lists at least four filament colors', async ({ page }) => {
    expect(await page.locator('input[type="color"]').count()).toBeGreaterThanOrEqual(4);
  });

  test('can add a filament color', async ({ page }) => {
    const colorInputs = page.locator('input[type="color"]');
    const initialCount = await colorInputs.count();

    await page.getByRole('button', { name: /Add Color/i }).click();

    await expect(colorInputs).toHaveCount(initialCount + 1);
  });

  test('can load a preset', async ({ page }) => {
    const presetSelect = page.getByRole('combobox', { name: 'Filament Preset' });
    await presetSelect.selectOption('bambu_cmyw');

    await expect(presetSelect).toHaveValue('bambu_cmyw');
    await expect(page.locator('input[type="color"]')).toHaveCount(4);
  });

  test('filament gamut preview section exists', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Achievable Filament Gamut' })).toBeVisible();
  });

  test('palette library section exists', async ({ page }) => {
    await expect(page.getByText(/Palette Library/i)).toBeVisible();
  });
});
