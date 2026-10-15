/** Inspect actual fox SVG geometry, finite motion and exported sizes in Edge. */
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import path from 'node:path';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const require = createRequire(path.join(root, 'apps/web/package.json'));
const { chromium } = require('@playwright/test');
const assets = path.join(root, 'apps/web/public/brand');
const output = path.join(root, 'artifacts/brand/fox-v1');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'msedge' });
try {
  const context = await browser.newContext({ viewport: { width: 1040, height: 960 },
    reducedMotion: 'no-preference', recordVideo: { dir: output, size: { width: 1040, height: 960 } } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(pathToFileURL(path.join(assets, 'fox-preview.html')).href);
  await page.locator('#motion').evaluate(img => img.decode());
  await page.getByRole('button', { name: '重播动画' }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(output, 'preview-desktop.png'), fullPage: true });
  const source = await page.locator('#motion').getAttribute('src');
  await page.getByRole('button', { name: '重播动画' }).press('Enter');
  assert.notEqual(await page.locator('#motion').getAttribute('src'), source);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForFunction(() => document.querySelector('#motion').getAttribute('src') === 'fox-mark.svg');
  await page.getByRole('button', { name: '重播动画' }).click();
  assert.equal(await page.locator('#motion').getAttribute('src'), 'fox-mark.svg');
  for (const width of [390, 640, 800, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: path.join(output, `preview-${width}.png`), fullPage: true });
  }
  assert.deepEqual(errors, []);
  const video = page.video();
  await context.close();
  await video.saveAs(path.join(output, 'fox-motion.webm'));

  const render = await browser.newPage({ viewport: { width: 512, height: 512 } });
  const mark = await readFile(path.join(assets, 'fox-mark.svg'), 'utf8');
  const motion = await readFile(path.join(assets, 'fox-motion.svg'), 'utf8');
  const icon = await readFile(path.join(assets, 'fox-icon.svg'), 'utf8');
  const monochrome = await readFile(path.join(assets, 'fox-monochrome.svg'), 'utf8');
  const paths = svg => [...svg.matchAll(/\sd="([^"]+)"/g)].map(value => value[1]);
  for (const svg of [motion, icon, monochrome]) assert.deepEqual(paths(svg), paths(mark));
  const style = '<style>html,body{margin:0;background:transparent}svg{display:block;width:100vw;height:100vh}</style>';
  await render.emulateMedia({ reducedMotion: 'no-preference' });
  await render.setContent(style + motion);
  await render.waitForTimeout(100);
  assert.notEqual(await render.locator('.route').evaluate(node => getComputedStyle(node).clipPath), 'none');
  await render.waitForTimeout(1500);
  assert.equal(await render.locator('.route').evaluate(node => getComputedStyle(node).clipPath), 'none');
  assert.equal(await render.locator('.fox').evaluate(node => getComputedStyle(node).opacity), '1');
  assert.equal(await render.evaluate(() => document.getAnimations().some(a => a.playState === 'running')), false);
  const completed = await render.screenshot({ path: path.join(output, 'completed-mark.png'), omitBackground: true });
  await render.setContent(style + mark);
  const staticMark = await render.screenshot({ path: path.join(assets, 'fox-mark-512.png'), omitBackground: true });
  assert.ok(completed.equals(staticMark), 'Completed motion must match the static mark');
  await render.setContent(style + motion);
  await render.emulateMedia({ reducedMotion: 'reduce' });
  assert.equal(await render.evaluate(() => document.getAnimations().length), 0);
  assert.equal(await render.locator('.route').evaluate(node => getComputedStyle(node).clipPath), 'none');
  // CSS unavailable: base SVG must still render exactly the full static geometry.
  await render.setContent(style + motion.replace(/<style>[\s\S]*?<\/style>/, ''));
  assert.ok((await render.screenshot({ omitBackground: true })).equals(staticMark), 'CSS fallback must match the static mark');
  for (const size of [16, 32, 48, 180, 512]) {
    await render.setViewportSize({ width: size, height: size });
    await render.setContent(style + icon);
    await render.screenshot({ path: path.join(assets, `fox-icon-${size}.png`), omitBackground: true });
  }
  await render.setViewportSize({ width: 960, height: 360 });
  await render.setContent(`<style>body{margin:0;display:flex}section{width:480px;height:360px;display:grid;place-items:center}svg{width:280px;height:280px}</style><section style="background:#F8F6F1">${mark}</section><section style="background:#2D2B27">${icon}</section>`);
  await render.screenshot({ path: path.join(output, 'backgrounds.png') });
  await render.close();
  await writeFile(path.join(output, 'verification.json'), JSON.stringify({ browser: 'Edge',
    geometryConsistent: true, completedEqualsStatic: true, finiteAnimation: true, replayKeyboard: true,
    dynamicReducedMotion: true, cssUnavailableStatic: true, widths: [390, 640, 800, 1440],
    pngSizes: [16, 32, 48, 180, 512], errors }, null, 2));
  process.stdout.write('Fox: shared paths, finite motion, static/reduce/fallback, keyboard and four widths passed.\n');
} finally {
  await browser.close();
}
