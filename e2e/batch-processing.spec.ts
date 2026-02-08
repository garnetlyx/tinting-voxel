import { test, expect } from '@playwright/test';
import { switchToBatchMode, TEST_IMAGE, TEST_IMAGE_2 } from './helpers';

test.describe('Batch Processing', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await switchToBatchMode(page);
  });

  test('batch mode shows upload area', async ({ page }) => {
    await expect(page.getByText(/Click to Select Images/)).toBeVisible();
    await expect(page.getByText(/PNG, JPEG, GIF, WebP, BMP/)).toBeVisible();
  });

  test('can upload multiple images', async ({ page }) => {
    const fileInput = page.locator('input[type="file"][multiple]');
    await fileInput.setInputFiles([TEST_IMAGE, TEST_IMAGE_2]);

    // Should show file count
    await expect(page.getByText(/2 images selected/)).toBeVisible();
  });

  test('can remove individual files', async ({ page }) => {
    const fileInput = page.locator('input[type="file"][multiple]');
    await fileInput.setInputFiles([TEST_IMAGE, TEST_IMAGE_2]);

    await expect(page.getByText(/2 images selected/)).toBeVisible();

    // Click first remove button (X icon)
    const removeButtons = page.locator('button').filter({
      has: page.locator('svg.lucide-x'),
    });
    await removeButtons.first().click();

    await expect(page.getByText(/1 image selected/)).toBeVisible();
  });

  test('can clear all files', async ({ page }) => {
    const fileInput = page.locator('input[type="file"][multiple]');
    await fileInput.setInputFiles([TEST_IMAGE, TEST_IMAGE_2]);

    await expect(page.getByText(/2 images selected/)).toBeVisible();

    await page.getByRole('button', { name: 'Clear All' }).click();

    // Upload area should be back, no file list
    await expect(page.getByText(/2 images selected/)).not.toBeVisible();
  });

  test('preview batch processes images', async ({ page }) => {
    const fileInput = page.locator('input[type="file"][multiple]');
    await fileInput.setInputFiles([TEST_IMAGE, TEST_IMAGE_2]);

    await page.getByRole('button', { name: 'Preview Batch' }).click();

    // Wait for processing complete
    await expect(page.getByText(/Batch Processing Complete/)).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/2 of 2 images processed successfully/)).toBeVisible();
  });

  test('can download batch STLs', async ({ page }) => {
    const fileInput = page.locator('input[type="file"][multiple]');
    await fileInput.setInputFiles([TEST_IMAGE]);

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /Download All STLs/ }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.zip$/);
  });

  test('can switch between single and batch modes', async ({ page }) => {
    await expect(page.getByText(/Click to Select Images/)).toBeVisible();

    // Switch to single mode
    await page.getByRole('button', { name: 'Single Image' }).click();
    await expect(page.getByText(/Click to Select Images/)).not.toBeVisible();
    await expect(page.getByText(/Click to Upload Image/)).toBeVisible();

    // Switch back to batch
    await page.getByRole('button', { name: 'Batch Processing' }).click();
    await expect(page.getByText(/Click to Select Images/)).toBeVisible();
  });
});
