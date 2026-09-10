/**
 * Prune-path E2E: Clear CMYWG palette at high layer counts (6 and 8) with the
 * 0.84 mm translucent layer-height default, driving the real UI. The clear
 * set is TD1S-transparent, so these runs exercise the composition-pruned
 * mapping path (see backend core/stack_prune.py).
 *
 * Requires backend/tests/fixtures/images-local/local-photo.JPG (gitignored local
 * fixture); the suite skips gracefully when it is absent.
 */
import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const LOCAL_PHOTO_IMAGE = path.join(__dirname, '../backend/tests/fixtures/images-local/local-photo.JPG');
const SHOT_DIR = path.join(__dirname, '../test-results/prune-clear-palette');

test.skip(!fs.existsSync(LOCAL_PHOTO_IMAGE), 'local-photo.JPG local fixture not present');

test.beforeAll(() => {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
});

for (const layerCount of [6, 8]) {
  test(`clear palette ${layerCount} layers @0.84mm renders via pruned path`, async ({ page }) => {
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
    await page.locator('select').nth(1).selectOption('clear_cmywg');
    await page.waitForTimeout(600);

    // Translucent classification raises the default layer height to 0.84 mm.
    const layerHeight = await page.locator('input[type=range][min="0.08"]').first().inputValue();
    expect(layerHeight).toBe('0.84');

    // Upload the real photo and process.
    const chooserP = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: /Click or drag image here/ }).click();
    (await chooserP).setFiles([LOCAL_PHOTO_IMAGE]);
    await page.waitForTimeout(1500);
    await page.getByRole('button', { name: 'Apply & Process' }).click();
    await page.waitForFunction(() => document.body.innerText.includes('Simulated Print'), null, {
      timeout: 240_000,
    });

    // Raise to the target layer count (default is 4).
    await page.evaluate(count => {
      const sliders = Array.from(document.querySelectorAll('input[type="range"]'));
      const t = sliders.find(s => s.min === '4' && s.step === '1') as HTMLInputElement;
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!;
      setter.call(t, String(count));
      t.dispatchEvent(new Event('input', { bubbles: true }));
      t.dispatchEvent(new Event('change', { bubbles: true }));
    }, layerCount);

    // The pruned mapping keeps high-layer reprocessing fast; still allow a
    // generous bound for the dev-server cold cache.
    await page.waitForFunction(
      () => document.body.innerText.includes('Reprocess'),
      null,
      { timeout: 240_000 },
    );
    await page.waitForTimeout(2_000);
    await page.screenshot({
      path: path.join(SHOT_DIR, `clear_${layerCount}L_pruned.png`),
      fullPage: true,
    });

    // No mapping/preview failures on the pruned path.
    expect(errors, errors.join(' | ')).toEqual([]);
  });
}
