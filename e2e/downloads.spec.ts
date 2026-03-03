import { test, expect } from '@playwright/test';
import { uploadAndProcess, waitForProcessingComplete, TEST_IMAGE_LARGE } from './helpers';

test.describe('Download Flows - Pixel Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await uploadAndProcess(page);
  });

  test('download buttons are visible after processing', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Download CSV/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Download STL/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Download 3MF/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Print Settings/ })).toBeVisible();
  });

  test('download CSV triggers file download', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /Download CSV/ }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.csv$/);
  });

  test('download STL triggers file download', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /Download STL/ }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.zip$/);
  });

  test('download 3MF triggers file download', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /Download 3MF/ }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.3mf$/);
  });

  test('download print settings triggers file download', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /Print Settings/ }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.json$/);
  });
});

test.describe('Download Flows - SVG Mode', () => {
  test('SVG mode hides CSV but shows 3MF button', async ({ page }) => {
    await page.goto('/');

    // Use larger image for SVG mode (small images produce contours below minArea threshold)
    await uploadAndProcess(page, TEST_IMAGE_LARGE);

    // Verify pixel mode buttons exist first
    await expect(page.getByRole('button', { name: /Download CSV/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Download 3MF/ })).toBeVisible();

    // Switch to SVG mode
    await page.getByRole('button', { name: /SVG/i }).first().click();

    // Click Reprocess to process in SVG mode
    await page.getByRole('button', { name: 'Reprocess' }).click();

    // Wait for SVG processing to complete
    await waitForProcessingComplete(page);

    // CSV should not be visible in SVG mode
    await expect(page.getByRole('button', { name: /Download CSV/ })).not.toBeVisible();

    // STL, 3MF, and Print Settings should be visible
    await expect(page.getByRole('button', { name: /Download STL/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Download 3MF/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Print Settings/ })).toBeVisible();
  });
});
