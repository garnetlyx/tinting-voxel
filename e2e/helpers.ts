import { Page, expect } from '@playwright/test';
import path from 'path';

export const FIXTURES_DIR = path.join(__dirname, 'fixtures');
export const TEST_IMAGE = path.join(FIXTURES_DIR, 'test-image.png');
export const TEST_IMAGE_2 = path.join(FIXTURES_DIR, 'test-image-2.png');
export const TEST_IMAGE_LARGE = path.join(FIXTURES_DIR, 'test-image-large.png');

/**
 * Upload a single image by setting files directly on the hidden input.
 * Playwright's setInputFiles dispatches the change event even on hidden inputs.
 */
export async function uploadImage(page: Page, imagePath: string = TEST_IMAGE) {
  // Target the single-mode file input (not multiple, which is batch mode)
  // Use a more specific selector to avoid matching the filament preset JSON input
  // The image uploader accepts image formats like image/png,image/jpeg,...
  const fileInput = page.locator('input[type="file"][accept^="image/png"]:not([multiple])');
  await fileInput.setInputFiles(imagePath);
}

/**
 * Upload an image and process it through the editor (Apply & Process)
 */
export async function uploadAndProcess(page: Page, imagePath: string = TEST_IMAGE) {
  await uploadImage(page, imagePath);

  // Wait for editor to appear
  await expect(page.getByRole('button', { name: /Apply & Process/ })).toBeVisible({
    timeout: 10_000,
  });

  // Click Apply & Process
  await page.getByRole('button', { name: /Apply & Process/ }).click();

  // Wait for processing to complete
  await waitForProcessingComplete(page);
}

/**
 * Wait for image processing to complete (spinner disappears, results visible)
 */
export async function waitForProcessingComplete(page: Page) {
  // Wait for results section to appear (download buttons are a reliable indicator)
  await page.getByRole('button', { name: /Download STL/ }).waitFor({
    state: 'visible',
    timeout: 30_000,
  });
}

/**
 * Switch to batch processing mode
 */
export async function switchToBatchMode(page: Page) {
  await page.getByRole('button', { name: 'Batch Processing' }).click();
}

/**
 * Switch to single image mode
 */
export async function switchToSingleMode(page: Page) {
  await page.getByRole('button', { name: 'Single Image' }).click();
}
