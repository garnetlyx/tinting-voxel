import { test, expect } from '@playwright/test';
import { uploadImage, uploadAndProcess } from './helpers';

test.describe('Single Image Processing', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('page loads with correct title and elements', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Image to STL/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Single Image' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Batch Processing' })).toBeVisible();
  });

  test('upload, process, and verify results', async ({ page }) => {
    await uploadImage(page);

    // Image editor should appear with Apply & Process button
    await expect(page.getByRole('button', { name: /Apply & Process/ })).toBeVisible({
      timeout: 10_000,
    });

    // Click Apply & Process to start processing
    await page.getByRole('button', { name: /Apply & Process/ }).click();

    // Wait for results
    await expect(page.getByRole('button', { name: /Download STL/ })).toBeVisible({ timeout: 30_000 });

    // Reprocess button should be visible
    await expect(page.getByRole('button', { name: 'Reprocess' })).toBeVisible();
  });

  test('parameter sliders are visible and adjustable', async ({ page }) => {
    // Settings panel is open by default
    await expect(page.getByText(/Max Colors:/)).toBeVisible();
    await expect(page.getByText(/Layer Height:/)).toBeVisible();
    await expect(page.getByText(/Pixel Size:/)).toBeVisible();
    await expect(page.getByText(/Base Plate Thickness:/)).toBeVisible();
  });

  test('can toggle settings panel visibility', async ({ page }) => {
    // Settings should be visible initially
    await expect(page.getByText(/Max Colors:/)).toBeVisible();

    // Click settings toggle button (the gear icon in the header)
    const settingsButton = page.locator('button').filter({
      has: page.locator('svg.lucide-settings'),
    });
    await settingsButton.click();

    // Settings should be hidden
    await expect(page.getByText(/Max Colors:/)).not.toBeVisible();

    // Click again to show
    await settingsButton.click();
    await expect(page.getByText(/Max Colors:/)).toBeVisible();
  });

  test('can switch between pixel and SVG modes', async ({ page }) => {
    // Default is pixel mode
    await expect(page.getByText(/Max Colors:/)).toBeVisible();

    // Switch to SVG mode
    await page.getByRole('button', { name: /SVG/i }).first().click();

    // SVG-specific params should appear
    await expect(page.getByText(/Number of Colors:/)).toBeVisible();
    await expect(page.getByText(/Simplification/)).toBeVisible();
    await expect(page.getByText(/Min Area:/)).toBeVisible();

    // Pixel-specific params should be hidden
    await expect(page.getByText(/Max Colors:/)).not.toBeVisible();
  });

  test('image editor cancel returns to upload state', async ({ page }) => {
    await uploadImage(page);

    // Editor should appear
    await expect(page.getByRole('button', { name: /Cancel/ })).toBeVisible({
      timeout: 10_000,
    });

    await page.getByRole('button', { name: /Cancel/ }).click();

    // After cancel, rawImage is cleared and isEditing is false.
    // Since image was never set via handleApplyEdit, the upload button should be visible again.
    await expect(page.getByRole('button', { name: 'Click to Upload Image' })).toBeVisible();

    // Editor should be gone
    await expect(page.getByRole('button', { name: /Apply & Process/ })).not.toBeVisible();
  });
});
