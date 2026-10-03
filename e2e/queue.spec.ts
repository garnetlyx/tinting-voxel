/**
 * Heavy-job queue UX: the over-budget confirmation dialog.
 *
 * The default five-color preset at ten color layers estimates an
 * unpaginated gamut preview over the server's memory budget
 * (5^10 combinations), so the filament preview is refused with a
 * job_to_large 422 and the browser must ask instead of failing.
 */
import { expect, test } from '@playwright/test';

test('asks before an over-budget preview and applies the scale-down', async ({ page }) => {
  await page.goto('/');

  // The color-layer slider appears once the filament set's layer limit loads.
  const layers = page.locator('input[type="range"][min="4"]');
  await expect(layers).toBeVisible({ timeout: 15_000 });
  await page.waitForFunction(() => {
    const slider = Array.from(document.querySelectorAll('input[type="range"]'))
      .find(s => s.min === '4' && s.step === '1') as HTMLInputElement;
    return slider && Number(slider.max) >= 10;
  });

  const retried = page.waitForResponse(
    resp => resp.url().includes('/api/filament-preview')
      && resp.request().method() === 'POST'
      && (resp.request().postData() ?? '').includes('"page":1'),
    { timeout: 20_000 },
  );

  await page.evaluate(() => {
    const slider = Array.from(document.querySelectorAll('input[type="range"]'))
      .find(s => s.min === '4' && s.step === '1') as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!;
    setter.call(slider, '10');
    slider.dispatchEvent(new Event('input', { bubbles: true }));
    slider.dispatchEvent(new Event('change', { bubbles: true }));
  });

  // The refusal becomes a modal question, not an error message.
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await expect(dialog).toContainText(/memory/i);

  await dialog.getByRole('button', { name: /apply suggestion/i }).click();

  const response = await retried;
  expect(response.status()).toBe(200);
  await expect(dialog).toBeHidden();
});

test('unknown job ids answer 404', async ({ request }) => {
  const response = await request.get('/api/jobs/not-a-job');
  expect(response.status()).toBe(404);
});
