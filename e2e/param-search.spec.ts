/**
 * E2E tests for the param search (Auto-Optimize Parameters) modal.
 * Covers: button visibility, modal open/close, config phase UI.
 * Does NOT run a full search (too slow for E2E); mocks the API response.
 */
import { test, expect } from '@playwright/test';
import { uploadAndProcess } from './helpers';

test.describe('Param Search Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('Auto-Optimize Parameters button is hidden before image upload', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Auto-Optimize Parameters/ })).not.toBeVisible();
  });

  test('Auto-Optimize Parameters button appears after processing an image', async ({ page }) => {
    await uploadAndProcess(page);
    await expect(page.getByRole('button', { name: /Auto-Optimize Parameters/ })).toBeVisible();
  });

  test('clicking Auto-Optimize Parameters opens the modal with config phase', async ({ page }) => {
    await uploadAndProcess(page);

    await page.getByRole('button', { name: /Auto-Optimize Parameters/ }).click();

    // Modal should be visible
    await expect(page.getByRole('dialog', { name: /Auto-Optimize Parameters/ })).toBeVisible();

    // Config phase elements
    await expect(page.getByLabel(/Target longest edge/)).toBeVisible();
    // No filament selector inside the search dialog (it reuses the
    // converter's current configuration).
    expect(await page.getByLabel(/Filament preset/).count()).toBe(0);
    await expect(page.getByRole('button', { name: /Start Optimization/ })).toBeVisible();
  });

  test('modal closes when clicking the ✕ button', async ({ page }) => {
    await uploadAndProcess(page);
    await page.getByRole('button', { name: /Auto-Optimize Parameters/ }).click();

    await expect(page.getByRole('dialog')).toBeVisible();

    // Click the header close button (aria-label="Close")
    await page.getByRole('button', { name: 'Close' }).first().click();

    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('modal closes on Escape key', async ({ page }) => {
    await uploadAndProcess(page);
    await page.getByRole('button', { name: /Auto-Optimize Parameters/ }).click();

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

    await page.getByRole('button', { name: /Auto-Optimize Parameters/ }).click();
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
    await page.getByRole('button', { name: /Auto-Optimize Parameters/ }).click();

    const sizeInput = page.getByLabel(/Target longest edge/);
    await sizeInput.fill('150');
    await expect(sizeInput).toHaveValue('150');
  });

  test('clicking Start Optimization transitions to running phase', async ({ page }) => {
    // Intercept the param-search API to return a mock response immediately
    await page.route('**/api/param-search', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'test-job-123',
          results: [
            {
              rank: 1,
              mode: 'pixel',
              params: { max_colors: 10, color_threshold: 40 },
              mae: 12.5,
              preview_image: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
            },
          ],
          total_evaluated: 1,
          elapsed_seconds: 0.1,
        }),
      });
    });

    // Also intercept SSE progress endpoint
    await page.route('**/api/param-search/progress/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"job_id":"test-job-123","completed":1,"total":1,"best_mae":12.5,"status":"complete"}\n\n',
      });
    });

    await uploadAndProcess(page);
    await page.getByRole('button', { name: /Auto-Optimize Parameters/ }).click();
    await page.getByRole('button', { name: /Start Optimization/ }).click();

    // Should show running or results phase (mock completes instantly)
    // Either the progress bar or results cards should appear
    await expect(
      page.getByText(/Searching for optimal parameters/).or(page.getByText(/Found \d+ results/))
    ).toBeVisible({ timeout: 5_000 });
  });
});
