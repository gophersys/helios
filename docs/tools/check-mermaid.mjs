// Parses every ```mermaid block in docs/ and documents/ (and the diagram template
// literals in render-atlas.mjs) with the real mermaid parser — the deterministic
// gate that keeps diagrams renderable (doc 12 §3: diagrams are projections; a
// diagram that does not parse is a broken projection).
// Usage: node docs/tools/check-mermaid.mjs   (requires mermaid + jsdom — devDependencies;
// NODE_PATH=/tmp/eden-render/node_modules works in this environment)
// Exit: 0 all blocks parse · 1 failures · 2 setup error

import { readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
// ESM import ignores NODE_PATH; anchor resolution there (or at the repo's
// node_modules) the same way the renderers resolve marked/mermaid.
const anchor = join(process.env.NODE_PATH ?? join(REPO, 'node_modules'), 'anchor.js');
const require = createRequire(anchor);

let mermaid;
try {
  const { JSDOM } = require('jsdom');
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', { pretendToBeVisual: true });
  global.window = dom.window;
  global.document = dom.window.document;
  mermaid = (await import(pathToFileURL(require.resolve('mermaid')))).default;
  mermaid.initialize({ startOnLoad: false, securityLevel: 'loose' });
} catch (error) {
  console.error(`setup failed (need mermaid + jsdom resolvable): ${error.message}`);
  process.exit(2);
}

const files = execSync(
  `find ${REPO}/docs ${REPO}/documents -name '*.md' -not -path '*attic*' 2>/dev/null`,
).toString().trim().split('\n').filter(Boolean);
files.push(`${REPO}/docs/tools/render-atlas.mjs`);

const blocks = [];
for (const file of files) {
  const text = readFileSync(file, 'utf8');
  let match;
  let index = 0;
  const fenced = /```mermaid\n([\s\S]*?)```/g;
  while ((match = fenced.exec(text))) blocks.push({ file, index: index++, source: match[1] });
  if (file.endsWith('.mjs')) {
    const literals = /`(flowchart[\s\S]*?)`/g;
    while ((match = literals.exec(text))) blocks.push({ file, index: index++, source: match[1] });
  }
}

let failures = 0;
for (const block of blocks) {
  const name = `${block.file.replace(`${REPO}/`, '')} #${block.index}`;
  try {
    await mermaid.parse(block.source);
    console.log(`ok    ${name}`);
  } catch (error) {
    failures += 1;
    const message = String(error.message || error).split('\n').slice(0, 3).join(' | ');
    console.log(`FAIL  ${name}: ${message}`);
  }
}
console.log(`${blocks.length} blocks, ${failures} failing`);
process.exit(failures === 0 ? 0 : 1);
