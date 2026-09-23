/**
 * E2E tests for the param search (Compare settings) modal.
 * Covers: button visibility, modal open/close, config phase UI.
 * The modal state test mocks the API; full-size search is verified separately
 * with the Local-photo image against the running service.
 */
import { test, expect } from '@playwright/test';
import { uploadAndProcess } from './helpers';

test.describe('Param Search Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('Compare settings button is hidden before image upload', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Compare settings/ })).not.toBeVisible();
  });

  test('Compare settings button appears after processing an image', async ({ page }) => {
    await uploadAndProcess(page);
    await expect(page.getByRole('button', { name: /Compare settings/ })).toBeVisible();
  });

  test('clicking Compare settings opens the modal with config phase', async ({ page }) => {
    await uploadAndProcess(page);

    await page.getByRole('button', { name: /Compare settings/ }).click();

    // Modal should be visible
    await expect(page.getByRole('dialog', { name: /Compare settings/ })).toBeVisible();

    // Config phase elements
    await expect(page.getByLabel(/Target longest edge/)).toBeVisible();
    // No filament selector inside the search dialog (it reuses the
    // converter's current configuration).
    expect(await page.getByLabel(/Filament preset/).count()).toBe(0);
    await expect(page.getByRole('button', { name: /Generate options/ })).toBeVisible();
  });

  test('modal closes when clicking the ✕ button', async ({ page }) => {
    await uploadAndProcess(page);
    await page.getByRole('button', { name: /Compare settings/ }).click();

    await expect(page.getByRole('dialog')).toBeVisible();

    // Click the header close button (aria-label="Close")
    await page.getByRole('button', { name: 'Close' }).first().click();

    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('modal closes on Escape key', async ({ page }) => {
    await uploadAndProcess(page);
    await page.getByRole('button', { name: /Compare settings/ }).click();

    await expect(page.getByRole('dialog')).toBeVisible();

    await page.keyboard.press('Escape');

    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('search reuses the converter’s current filament configuration', async ({ page }) => {
    // The modal carries no preset selector (removed by design): the search
    // runs against whatever the main UI has selected. With Clear CMYW
    // active, starting a search must not reset the converter configuration.
    await uploadAndProcess(page);
    await page.locator('select').nth(1).selectOption('clear_cmyw');
    await page.waitForTimeout(600);

    await page.getByRole('button', { name: /Compare settings/ }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    expect(await page.getByLabel(/Filament preset/).count()).toBe(0);
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();

    // The converter still runs the Clear CMYW preset.
    const selected = await page.locator('select').nth(1).inputValue();
    expect(selected).toBe('clear_cmyw');
  });

  test('target size input accepts numeric input', async ({ page }) => {
    await uploadAndProcess(page);
    await page.getByRole('button', { name: /Compare settings/ }).click();

    const sizeInput = page.getByLabel(/Target longest edge/);
    await sizeInput.fill('150');
    await expect(sizeInput).toHaveValue('150');
  });

  test('clicking Generate options transitions to running phase', async ({ page }) => {
    // Starting a search returns a job immediately; previews arrive in polls.
    await page.route('**/api/param-search', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'test-job-123',
          completed: 0,
          total: 21,
          status: 'running',
          results: [
          ],
        }),
      });
    });

    // The first completed full-resolution preview becomes visible while the
    // remaining evaluations are still running.
    await page.route('**/api/param-search/progress/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'test-job-123', completed: 1, total: 21, status: 'running', error: null,
          results: [{
            candidate_id: 1, is_baseline: true, mode: 'pixel',
            params: { max_colors: 10, color_threshold: 40 },
            preview_image: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
          }],
        }),
      });
    });

    await uploadAndProcess(page);
    await page.getByRole('button', { name: /Compare settings/ }).click();
    await page.getByRole('button', { name: /Generate options/ }).click();

    await expect(page.getByAltText('Current settings')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('1 / 21')).toBeVisible();
  });
});
