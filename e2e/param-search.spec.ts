/**
 * E2E tests for the param search (自动优化参数) modal.
 * Covers: button visibility, modal open/close, config phase UI.
 * Does NOT run a full search (too slow for E2E); mocks the API response.
 */
import { test, expect } from '@playwright/test';
import { uploadAndProcess } from './helpers';

test.describe('Param Search Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('自动优化参数 button is hidden before image upload', async ({ page }) => {
    await expect(page.getByRole('button', { name: /自动优化参数/ })).not.toBeVisible();
  });

  test('自动优化参数 button appears after processing an image', async ({ page }) => {
    await uploadAndProcess(page);
    await expect(page.getByRole('button', { name: /自动优化参数/ })).toBeVisible();
  });

  test('clicking 自动优化参数 opens the modal with config phase', async ({ page }) => {
    await uploadAndProcess(page);

    await page.getByRole('button', { name: /自动优化参数/ }).click();

    // Modal should be visible
    await expect(page.getByRole('dialog', { name: /自动优化参数/ })).toBeVisible();

    // Config phase elements
    await expect(page.getByLabel(/目标最长边尺寸/)).toBeVisible();
    await expect(page.getByLabel(/色丝预设/)).toBeVisible();
    await expect(page.getByRole('button', { name: /开始优化/ })).toBeVisible();
  });

  test('modal closes when clicking the ✕ button', async ({ page }) => {
    await uploadAndProcess(page);
    await page.getByRole('button', { name: /自动优化参数/ }).click();

    await expect(page.getByRole('dialog')).toBeVisible();

    // Click the header close button (aria-label="关闭")
    await page.getByRole('button', { name: '关闭' }).first().click();

    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('modal closes on Escape key', async ({ page }) => {
    await uploadAndProcess(page);
    await page.getByRole('button', { name: /自动优化参数/ }).click();

    await expect(page.getByRole('dialog')).toBeVisible();

    await page.keyboard.press('Escape');

    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('preset selector has expected options', async ({ page }) => {
    await uploadAndProcess(page);
    await page.getByRole('button', { name: /自动优化参数/ }).click();

    const select = page.getByLabel(/色丝预设/);
    await expect(select).toBeVisible();

    // Check a few preset options exist
    await expect(select.locator('option', { hasText: 'Bambu CMYW Phase 6' })).toHaveCount(1);
    await expect(select.locator('option', { hasText: 'Clear CMYW' })).toHaveCount(1);
  });

  test('target size input accepts numeric input', async ({ page }) => {
    await uploadAndProcess(page);
    await page.getByRole('button', { name: /自动优化参数/ }).click();

    const sizeInput = page.getByLabel(/目标最长边尺寸/);
    await sizeInput.fill('150');
    await expect(sizeInput).toHaveValue('150');
  });

  test('clicking 开始优化 transitions to running phase', async ({ page }) => {
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
    await page.getByRole('button', { name: /自动优化参数/ }).click();
    await page.getByRole('button', { name: /开始优化/ }).click();

    // Should show running or results phase (mock completes instantly)
    // Either the progress bar or results cards should appear
    await expect(
      page.getByText(/正在搜索最优参数/).or(page.getByText(/找到.*个结果/))
    ).toBeVisible({ timeout: 5_000 });
  });
});
