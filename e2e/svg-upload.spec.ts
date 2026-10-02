import { test, expect } from '@playwright/test';
import path from 'path';
import { uploadImage, waitForProcessingComplete } from './helpers';

// The site's own logo: a viewBox-only SVG with no width or height.
const BRAND_SVG = path.join(__dirname, '../public/brand.svg');

test.describe('SVG upload', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('vector mode accepts an SVG file and processes it', async ({ page }) => {
    await page.getByRole('button', { name: /Vector/i }).first().click();
    await uploadImage(page, BRAND_SVG);

    // Rasterized at full size rather than the 64 px viewBox.
    await expect(page.getByText('2048 x 2048 px')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/Unsupported file type/)).not.toBeVisible();

    await page.getByRole('button', { name: /Apply & Process/ }).click();
    await waitForProcessingComplete(page);
    await expect(page.getByRole('button', { name: /Download 3MF/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Download CSV/ })).not.toBeVisible();
  });

  test('pixel mode accepts an SVG file and processes it', async ({ page }) => {
    await uploadImage(page, BRAND_SVG);
    await expect(page.getByText('2048 x 2048 px')).toBeVisible({ timeout: 10_000 });

    await page.getByRole('button', { name: /Apply & Process/ }).click();
    await waitForProcessingComplete(page);
    await expect(page.getByRole('button', { name: /Download CSV/ })).toBeVisible();
  });

  test('a malformed SVG shows a load error', async ({ page }) => {
    const fileInput = page.locator('input[type="file"][accept^="image/png"]:not([multiple])');
    await fileInput.setInputFiles({ name: 'broken.svg', mimeType: 'image/svg+xml', buffer: Buffer.from('<svg') });

    await expect(page.getByText(/Failed to load image/)).toBeVisible();
    await expect(page.getByRole('button', { name: /Apply & Process/ })).not.toBeVisible();
  });
});
