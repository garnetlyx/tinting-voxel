import { test, expect } from '@playwright/test';
import { uploadAndProcess } from './helpers';

// Use software WebGL so preview capture also runs on headless CI machines.
test.use({ launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } });

test('submits conversion diagnostics without attaching an image by default', async ({ page }) => {
  await page.route('**/api/bug-report', route => route.fulfill({ json: { success: true, reportId: 'browser-report', delivery: 'stored' } }));
  await page.goto('/?token=private#private');
  await page.getByRole('button', { name: 'Report a bug', exact: true }).click();
  await expect(page.getByRole('textbox', { name: /What happened/ })).toBeFocused();
  await expect(page.getByRole('checkbox', { name: /Include a screenshot/ })).not.toBeChecked();
  await page.getByRole('textbox', { name: /What happened/ }).fill('Preview looks wrong');
  const requestPromise = page.waitForRequest('**/api/bug-report');
  await page.getByRole('button', { name: 'Send report', exact: true }).click();
  const payload = (await requestPromise).postDataJSON();
  expect(payload.description).toBe('Preview looks wrong');
  expect(payload.screenshot).toBeUndefined();
  expect(payload.frontendContext.url).not.toContain('private');
  expect(payload.frontendContext.converter.layerCount).toBe(4);
  await expect(page.getByRole('status')).toContainText('browser-report');
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Report a bug', exact: true })).toBeFocused();
});

test('captures a viewport screenshot with a populated 3D preview', async ({ page }) => {
  await page.route('**/api/bug-report', route => route.fulfill({ json: { success: true, reportId: 'screenshot-report', delivery: 'stored' } }));
  await page.goto('/');
  await uploadAndProcess(page);
  await page.getByRole('heading', { name: '3D Preview', exact: true }).scrollIntoViewIfNeeded();
  await page.getByRole('button', { name: 'Report a bug', exact: true }).click();
  await page.getByRole('checkbox', { name: /Include a screenshot/ }).check();
  const requestPromise = page.waitForRequest('**/api/bug-report');
  await page.getByRole('button', { name: 'Send report', exact: true }).click();
  const payload = (await requestPromise).postDataJSON();
  expect(payload.screenshot).toMatch(/^data:image\/jpeg;base64,/);
  expect(payload.screenshot.length).toBeLessThan(4 * 1024 * 1024);
  expect(payload.frontendContext.converter.imageWidth).toBeGreaterThan(0);
  const dimensions = await page.evaluate(async screenshot => {
    const image = new Image();
    image.src = screenshot;
    await image.decode();
    return { width: image.width, height: image.height };
  }, payload.screenshot);
  const viewport = page.viewportSize()!;
  expect(dimensions.width).toBe(Math.floor(viewport.width * Math.min(1, 1440 / viewport.width)));
  expect(dimensions.height).toBe(Math.floor(viewport.height * Math.min(1, 1440 / viewport.width)));
  await expect(page.getByRole('status')).toContainText('screenshot-report');
});

test('retains feedback on failure and supports retry on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let attempts = 0;
  await page.route('**/api/bug-report', route => {
    attempts++;
    return attempts === 1
      ? route.fulfill({ status: 503, json: { detail: 'Please try again later.' } })
      : route.fulfill({ json: { success: true, reportId: 'retry-report', delivery: 'stored' } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Report a bug', exact: true }).click();
  const dialog = page.getByRole('dialog');
  const box = await dialog.boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  expect(box!.y + box!.height).toBeLessThanOrEqual(844);
  await page.getByRole('textbox', { name: /What happened/ }).fill('Mobile conversion issue');
  await page.getByRole('button', { name: 'Send report', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('try again');
  await expect(page.getByRole('textbox', { name: /What happened/ })).toHaveValue('Mobile conversion issue');
  await page.getByRole('button', { name: 'Send report', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('retry-report');
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
});
