/**
 * The forced-oversize hard cap (guard for the 2026-10-20 OOM crash).
 *
 * Runs via playwright.oversize.config.ts, which starts the backend with
 * HEAVY_MEMORY_BUDGET_MB=80 and a cap chosen per run:
 *
 * - cap 95 MB (default): the default preset's seven-layer preview estimates
 *   105 MB, over budget AND past the cap, so the dialog must drop the
 *   "Run anyway" button and only the scale-down may proceed.
 * - cap 200 MB (E2E_FORCE_ALLOWED=1): the same job is over budget but under
 *   the cap, so "Run anyway" stays available and forcing must run it.
 */
import { expect, test } from '@playwright/test';

const FORCE_ALLOWED = process.env.E2E_FORCE_ALLOWED === '1';

async function setLayers(page: import('@playwright/test').Page, value: string): Promise<void> {
  await page.evaluate(v => {
    const slider = Array.from(document.querySelectorAll('input[type="range"]'))
      .find(s => s.min === '4' && s.step === '1') as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!;
    setter.call(slider, v);
    slider.dispatchEvent(new Event('input', { bubbles: true }));
    slider.dispatchEvent(new Event('change', { bubbles: true }));
  }, value);
}

test('over-budget past the hard cap offers no run-anyway', async ({ page }) => {
  test.skip(FORCE_ALLOWED, 'runs only with the cap below the estimate');
  await page.goto('/');

  const layers = page.locator('input[type="range"][min="4"]');
  await expect(layers).toBeVisible({ timeout: 15_000 });
  await page.waitForFunction(() => {
    const slider = Array.from(document.querySelectorAll('input[type="range"]'))
      .find(s => s.min === '4' && s.step === '1') as HTMLInputElement;
    return slider && Number(slider.max) >= 7;
  });

  const retried = page.waitForResponse(
    resp => resp.url().includes('/api/filament-preview')
      && resp.request().method() === 'POST'
      && (resp.request().postData() ?? '').includes('"page":1'),
    { timeout: 20_000 },
  );

  await setLayers(page, '7');

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await expect(dialog).toContainText(/memory/i);
  await expect(dialog.getByRole('button', { name: /run anyway/i })).toHaveCount(0);

  await dialog.getByRole('button', { name: /apply suggestion/i }).click();
  expect((await retried).status()).toBe(200);
  await expect(dialog).toBeHidden();
});

test('over-budget under the cap keeps run-anyway and forcing runs it', async ({ page }) => {
  test.skip(!FORCE_ALLOWED, 'runs only with the cap above the estimate');
  await page.goto('/');

  const layers = page.locator('input[type="range"][min="4"]');
  await expect(layers).toBeVisible({ timeout: 15_000 });
  await page.waitForFunction(() => {
    const slider = Array.from(document.querySelectorAll('input[type="range"]'))
      .find(s => s.min === '4' && s.step === '1') as HTMLInputElement;
    return slider && Number(slider.max) >= 7;
  });

  const forced = page.waitForResponse(
    resp => resp.url().includes('/api/filament-preview')
      && resp.request().method() === 'POST'
      && (resp.request().postData() ?? '').includes('"forceOversize":true'),
    { timeout: 20_000 },
  );

  await setLayers(page, '7');

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await expect(dialog).toContainText(/memory/i);
  const runAnyway = dialog.getByRole('button', { name: /run anyway/i });
  await expect(runAnyway).toBeVisible();

  await runAnyway.click();
  expect([200, 202]).toContain((await forced).status());
  await expect(dialog).toBeHidden({ timeout: 20_000 });
});
