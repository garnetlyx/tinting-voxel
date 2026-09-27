/**
 * Clear-palette E2E: Clear CMYW at high layer counts (6 and 8) with the
 * 0.84 mm translucent layer-height default, driving the real UI. The clear
 * set is transparent by the fixed td threshold; at these sizes the
 * time-budget enumeration decision takes the full path (4c x 8L = 65,536
 * codes fits the budget; composition pruning engages only over budget).
 *
 * Each layer-count change is verified against its specific
 * /api/simulate-preview network response (request body carries layerCount),
 * and the returned preview must re-render — no fixed waits, no accepting an
 * already-present image. Requests cannot leak between tests: every layer
 * change awaits its own response.
 *
 * Requires a photo in backend/tests/fixtures/images-local/ (gitignored local
 * fixture); the suite skips gracefully when there is none.
 */
import { test, expect, Page } from '@playwright/test';
import { localPhoto } from './helpers';

const PHOTO = localPhoto();

test.skip(PHOTO === undefined, 'no photo in the local fixture folder');

/**
 * Set the layer-count slider and wait for the /api/simulate-preview response
 * carrying that exact layerCount in its multipart body, then for a fresh
 * Simulated Print render.
 */
async function setLayersAndWaitForPreview(page: Page, layerCount: number) {
  const srcBefore = await page.locator('img[alt="Processed"]').getAttribute('src');
  const responsePromise = page.waitForResponse(async resp => {
    if (!resp.url().includes('/api/simulate-preview')) return false;
    const body = resp.request().postData() ?? '';
    if (!body.includes(`"layerCount":"${layerCount}"`) && !body.includes(`layerCount"${layerCount}`) && !new RegExp(`layerCount[^0-9]{0,3}${layerCount}([^0-9]|$)`).test(body)) return false;
    return true;
  }, { timeout: 240_000 });

  await page.evaluate(count => {
    const t = Array.from(document.querySelectorAll('input[type="range"]'))
      .find(s => s.min === '4' && s.step === '1') as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!;
    setter.call(t, String(count));
    t.dispatchEvent(new Event('input', { bubbles: true }));
    t.dispatchEvent(new Event('change', { bubbles: true }));
  }, layerCount);

  const resp = await responsePromise;
  expect(resp.status(), `simulate-preview layerCount=${layerCount}`).toBe(200);

  // The returned preview must actually render: wait until the Processed image
  // is replaced with a new data URL from this response.
  await page.waitForFunction(
    (prev: string | null) => {
      const img = document.querySelector('img[alt="Processed"]') as HTMLImageElement | null;
      return !!img?.src && img.src !== prev;
    },
    srcBefore,
    { timeout: 60_000 },
  );
  await expect(page.locator('img[alt="Processed"]')).toBeVisible();
}

for (const layerCount of [6, 8]) {
  test(`clear palette ${layerCount} layers @0.84mm renders via time-budgeted path`, async ({ page }) => {
    test.setTimeout(300_000); // 0.84mm processing of the full photo takes >60s under E2E load
    const errors: string[] = [];
    page.on('console', m => {
      if (m.type() !== 'error') return;
      // The optional three.js 3D preview cannot create a WebGL context under
      // headless SwiftShader; the 2D simulated print is unaffected.
      if (m.text().includes('WebGLRenderer')) return;
      errors.push(m.text());
    });
    page.on('response', r => {
      if (r.url().includes('/api/') && r.status() >= 400) {
        errors.push(`${r.status()} ${r.url()}`);
      }
    });

    await page.goto('/');
    await page.getByRole('combobox', { name: 'Filament Preset' }).selectOption('clear_cmyw');
    await page.waitForTimeout(600);

    // Translucent classification raises the default layer height to 0.84 mm.
    const layerHeight = await page.locator('input[type=range][min="0.08"]').first().inputValue();
    expect(layerHeight).toBe('0.84');

    // Upload the real photo and process (default 4 layers).
    const chooserP = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: /Click or drag image here/ }).click();
    (await chooserP).setFiles([PHOTO!]);
    await page.waitForTimeout(1500);
    await page.getByRole('button', { name: 'Apply & Process' }).click();
    await page.waitForFunction(() => document.body.innerText.includes('Simulated Print'), null, {
      timeout: 240_000,
    });

    // Raise to the target layer count and verify THAT request completes and
    // its returned preview renders.
    await setLayersAndWaitForPreview(page, layerCount);

    await page.screenshot({
      path: test.info().outputPath(`clear_${layerCount}L.png`),
      fullPage: true,
    });

    // No mapping/preview failures on the time-budgeted path.
    expect(errors, errors.join(' | ')).toEqual([]);
  });
}
