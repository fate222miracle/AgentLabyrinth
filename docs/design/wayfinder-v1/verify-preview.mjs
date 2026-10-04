/** Render the actual local SVG assets and inspect the finite brand animation in Edge. */
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import path from 'node:path';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const require = createRequire(path.join(root, 'apps/web/package.json'));
const { chromium } = require('@playwright/test');
const assets = path.join(root, 'apps/web/public/brand');
const output = path.join(root, 'artifacts/brand/wayfinder-v1');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'msedge' });
const context = await browser.newContext({ viewport: { width: 1000, height: 720 },
  reducedMotion: 'no-preference', recordVideo: { dir: output, size: { width: 1000, height: 720 } } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const previewUrl = pathToFileURL(path.join(assets, 'preview.html')).href;
try {
  await page.goto(previewUrl);
  await page.locator('#motion').evaluate(img => img.decode());
  await page.getByRole('button', { name: '重播动画' }).click();
  await page.waitForTimeout(1800);
  await page.screenshot({ path: path.join(output, 'brand-preview-desktop.png') });
  const video = page.video();
  const source = await page.locator('#motion').getAttribute('src');
  await page.getByRole('button', { name: '重播动画' }).press('Enter');
  assert.notEqual(await page.locator('#motion').getAttribute('src'), source);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForFunction(() => document.querySelector('#motion').getAttribute('src') === 'wayfinder-mark.svg');
  assert.match(await page.locator('#preference').innerText(), /静态/);
  await page.getByRole('button', { name: '重播动画' }).click();
  assert.equal(await page.locator('#motion').getAttribute('src'), 'wayfinder-mark.svg');
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: path.join(output, 'brand-preview-mobile.png'), fullPage: true });
  assert.deepEqual(errors, []);
  await context.close();
  await video.saveAs(path.join(output, 'brand-motion.webm'));

  const render = await browser.newPage();
  const mark = await readFile(path.join(assets, 'wayfinder-mark.svg'), 'utf8');
  const motion = await readFile(path.join(assets, 'wayfinder-motion.svg'), 'utf8');
  const icon = await readFile(path.join(assets, 'wayfinder-icon.svg'), 'utf8');
  const geometry = /\sd="([^"]+)"/g;
  assert.deepEqual([...mark.matchAll(geometry)].map(m => m[1]), [...motion.matchAll(geometry)].map(m => m[1]));
  assert.deepEqual([...mark.matchAll(geometry)].map(m => m[1]), [...icon.matchAll(geometry)].map(m => m[1]));
  await render.emulateMedia({ reducedMotion: 'no-preference' });
  await render.setContent(`<style>svg{width:256px;height:256px}</style>${motion}`);
  await render.waitForTimeout(100);
  const early = await render.locator('.route').evaluate(node => getComputedStyle(node).strokeDashoffset);
  await render.waitForTimeout(1800);
  assert.equal(await render.locator('.route').evaluate(node => getComputedStyle(node).strokeDashoffset), '0px');
  assert.equal(await render.locator('.exit').evaluate(node => getComputedStyle(node).opacity), '1');
  assert.equal(await render.evaluate(() => document.getAnimations().some(animation => animation.playState === 'running')), false);
  assert.notEqual(early, '0px');
  await render.emulateMedia({ reducedMotion: 'reduce' });
  await render.setContent(motion);
  assert.equal(await render.evaluate(() => document.getAnimations().length), 0);

  for (const size of [16, 32, 48, 180, 512]) {
    await render.setViewportSize({ width: size, height: size });
    await render.setContent(`<style>html,body{margin:0;background:transparent}svg{display:block;width:${size}px;height:${size}px}</style>${icon}`);
    await render.screenshot({ path: path.join(assets, `wayfinder-icon-${size}.png`), omitBackground: true });
  }
  await render.setViewportSize({ width: 512, height: 512 });
  await render.setContent(`<style>html,body{margin:0;background:transparent}svg{display:block;width:512px;height:512px}</style>${mark}`);
  await render.screenshot({ path: path.join(assets, 'wayfinder-mark-512.png'), omitBackground: true });
  await render.close();
  await writeFile(path.join(output, 'verification.json'), JSON.stringify({ browser: 'Edge',
    geometryConsistent: true, finiteAnimation: true, replayKeyboard: true, dynamicReducedMotion: true,
    mobileWidth: 390, overflow: false, pngSizes: [16, 32, 48, 180, 512], errors }, null, 2));
  process.stdout.write('Wayfinder: geometry, finite motion, replay, reduce, 390px and PNG exports passed.\n');
} finally {
  await browser.close();
}
