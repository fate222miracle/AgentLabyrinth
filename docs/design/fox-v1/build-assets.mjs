/** Derive production variants from the single fox master; no bitmap tracing at runtime. */
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const assets = fileURLToPath(new URL('../../../apps/web/public/brand/', import.meta.url));
const mark = await readFile(path.join(assets, 'fox-mark.svg'), 'utf8');
const monochrome = mark.replaceAll('#C96442', '#2D2B27');
const icon = mark.replace('<g class="fox">',
  '<rect x="65" y="180" width="760" height="760" rx="160" fill="#A6492D" />\n  <g class="fox" transform="translate(445 560) scale(.82) translate(-445 -560)">')
  .replaceAll('#C96442', '#FFFDF9').replaceAll('#2D2B27', '#FFFDF9');
const motion = mark.replace('</title>', ' · 动态展示</title>').replace('  <defs>', `  <style>
    .fox { transform-box: fill-box; transform-origin: center; animation: appear 560ms cubic-bezier(.2,.7,.2,1) backwards; }
    .features { animation: focus 300ms ease-out 180ms backwards; }
    .route { animation: trace-route 950ms cubic-bezier(.25,.6,.2,1) 380ms backwards; }
    @keyframes appear { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
    @keyframes focus { from { opacity: 0; } to { opacity: 1; } }
    @keyframes trace-route { from { clip-path: inset(0 100% 0 0); } 99.9% { clip-path: inset(0 0% 0 0); } to { clip-path: none; } }
    @media (prefers-reduced-motion: reduce) { .fox, .features, .route { animation: none; } }
  </style>
  <defs>`);
// Replay the same 1330 ms sequence with a 670 ms hold.
const loading = mark.replace('  <defs>', `  <style>
    .fox { transform-box: fill-box; transform-origin: center; animation: loading-appear 2s cubic-bezier(.2,.7,.2,1) infinite; }
    .features { animation: loading-focus 2s ease-out infinite; }
    .route { animation: loading-trace 2s cubic-bezier(.25,.6,.2,1) infinite; }
    @keyframes loading-appear {
      0% { opacity: 0; transform: translateY(12px); }
      28%, 100% { opacity: 1; transform: none; }
    }
    @keyframes loading-focus { 0%, 9% { opacity: 0; } 24%, 100% { opacity: 1; } }
    @keyframes loading-trace {
      0%, 19% { clip-path: inset(0 100% 0 0); }
      66.45% { clip-path: inset(0 0% 0 0); }
      66.5%, 100% { clip-path: none; }
    }
    @media (prefers-reduced-motion: reduce) { .fox, .features, .route { animation: none; } }
  </style>
  <defs>`);
for (const [name, svg] of [['fox-monochrome', monochrome], ['fox-icon', icon], ['fox-motion', motion], ['fox-loading', loading]]) {
  await writeFile(path.join(assets, `${name}.svg`), svg);
}
process.stdout.write('Fox static, monochrome, app icon and motion share the master paths.\n');
