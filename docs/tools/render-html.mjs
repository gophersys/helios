// Renders docs/architecture/ into a single self-contained HTML reading copy.
// Usage: node docs/tools/render-html.mjs   (requires `marked` — `yarn install` provides it;
// or run with NODE_PATH pointing at any node_modules that contains marked@15)
// Output: docs/architecture/eden-architecture.html (gitignored; never edit by hand)

import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let marked;
try {
  ({ marked } = require('marked'));
} catch {
  console.error('marked not found — run `yarn install` (it is a devDependency), or set NODE_PATH.');
  process.exit(1);
}

// Locate the self-contained mermaid browser bundle (mermaid.min.js, ~3.3 MB) so it can be
// inlined into the output and keep the HTML offline. Resolved via the same require used for
// marked, so NODE_PATH / node_modules discovery is identical.
function mermaidBundlePath() {
  try {
    return require.resolve('mermaid/dist/mermaid.min.js');
  } catch {
    return null;
  }
}

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'architecture');
const OUT = `${ROOT}/eden-architecture.html`;
const GENERATED = new Date().toISOString().slice(0, 10);

// The manifest is derived from the filesystem so new docs/ADRs self-heal on regen. Ordering is
// preserved deterministically: README first, numbered specs ascending by NN, open-decisions last,
// then ADRs ascending by NNNN. The `id` MUST stay derived from the filename stem (d-<stem> /
// d-adr-<NNNN>) — rewriteLinks() rewrites cross-doc links onto exactly those anchors.
//
// Excluded by design: README/open-decisions are placed explicitly (not auto-listed among the
// numbered specs); handoff-* are transient working artifacts (not canonical specs); adr/template.md
// is the ADR stencil (no NNNN prefix); the generated *.html reading copies are never re-ingested.
const firstHeading = (file) => {
  const m = readFileSync(`${ROOT}/${file}`, 'utf8').match(/^#\s+(.+?)\s*$/m);
  return m ? m[1].trim() : file;
};
// Strip the leading "NN — " / "NN - " or "ADR-NNNN: " ordinal so the nav label reads cleanly.
const navLabel = (file) => firstHeading(file)
  .replace(/^\d{2}\s*[—–-]\s*/, '')
  .replace(/^ADR-\d{4}:\s*/i, '');

const numberedSpecs = readdirSync(ROOT)
  .filter((f) => /^\d{2}-[a-z0-9-]+\.md$/.test(f))
  .sort((a, b) => Number(a.slice(0, 2)) - Number(b.slice(0, 2)))
  .map((file) => ({ id: `d-${file.replace(/\.md$/, '')}`, file, nav: navLabel(file), chip: file.slice(0, 2) }));

const adrDocs = readdirSync(`${ROOT}/adr`)
  .filter((f) => /^\d{4}-[a-z0-9-]+\.md$/.test(f))
  .sort((a, b) => Number(a.slice(0, 4)) - Number(b.slice(0, 4)))
  .map((f) => {
    const num = f.slice(0, 4);
    return { id: `d-adr-${num}`, file: `adr/${f}`, nav: navLabel(`adr/${f}`), chip: `ADR-${num}`, adr: true };
  });

const DOCS = [
  { id: 'd-readme', file: 'README.md', nav: 'Overview & doc map', chip: 'README' },
  ...numberedSpecs,
  { id: 'd-open-decisions', file: 'open-decisions.md', nav: 'Open decisions', chip: 'OD' },
  ...adrDocs,
];

marked.use({ gfm: true });

const rewriteLinks = (md) => md
  .replace(/\]\((?:\.\/)?([0-9]{2}-[a-z0-9-]+)\.md\)/g, '](#d-$1)')
  .replace(/\]\(open-decisions\.md\)/g, '](#d-open-decisions)')
  .replace(/\]\(README\.md\)/g, '](#d-readme)')
  .replace(/\]\(adr\/([0-9]{4})[a-z0-9.-]*\.md\)/g, '](#d-adr-$1)')
  .replace(/\]\(adr\/\)/g, '](#d-adr-0001)');

const slug = (s) => s.replace(/<[^>]+>/g, '').toLowerCase()
  .replace(/&amp;/g, 'and').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60);

// marked renders a ```mermaid fence as <pre><code class="language-mermaid">…</code></pre>.
// mermaid's browser API expects the source in <pre class="mermaid">…</pre>, so rewrite those
// blocks (and only those). Returns { html, count } so the caller knows whether any diagrams
// exist (the ~3.3 MB mermaid bundle is only inlined when at least one block is present).
const MERMAID_BLOCK_RE =
  /<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g;
function transformMermaid(html) {
  let count = 0;
  const out = html.replace(MERMAID_BLOCK_RE, (_, body) => {
    count++;
    // marked HTML-escapes the fence body (&lt; &amp; …); mermaid wants the raw source, so
    // decode the entities marked introduced. Source text is then re-parsed by mermaid itself.
    const src = body
      .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
    return `<pre class="mermaid">${src}</pre>`;
  });
  return { html: out, count };
}

const sections = [];
const navEntries = [];
let mermaidCount = 0;

for (const d of DOCS) {
  const raw = readFileSync(`${ROOT}/${d.file}`, 'utf8');
  let html = marked.parse(rewriteLinks(raw));
  const mm = transformMermaid(html);
  html = mm.html;
  mermaidCount += mm.count;
  html = html.replace(/<table>/g, '<div class="tw"><table>').replace(/<\/table>/g, '</table></div>');
  const subs = [];
  html = html.replace(/<h2>([\s\S]*?)<\/h2>/g, (_, inner) => {
    const id = `${d.id}--${slug(inner)}`;
    subs.push({ id, label: inner.replace(/<[^>]+>/g, '') });
    return `<h2 id="${id}">${inner}</h2>`;
  });
  sections.push(`<section id="${d.id}" class="doc${d.adr ? ' adr' : ''}">\n<div class="chip">${d.chip}</div>\n${html}\n</section>`);
  navEntries.push({ ...d, subs });
}

const css = `
/* Eden visual identity (documents/design-system/tokens.json, intake C21) — light-first,
   with a dark variant derived from the SAME five locked colors:
     Bone #F4F1E8 · Ink #1A1A1A · Deep Forest #243D2C · Moss #5C7F5C · Sage #A8B89C.
   Every working token below resolves to one of those five or a token-derived alpha. */
:root{
  --color-bone:#f4f1e8; --color-ink:#1a1a1a; --color-deep-forest:#243d2c;
  --color-moss:#5c7f5c; --color-sage:#a8b89c;
  --color-background:var(--color-bone); --color-text:var(--color-ink);
  --color-surface-primary:var(--color-deep-forest); --color-text-on-surface:var(--color-bone);
  --color-accent:var(--color-moss); --color-support:var(--color-sage);
  --font-display:'Fraunces',Georgia,serif;
  --font-text:'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --font-code:'JetBrains Mono',ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --bg:var(--color-bone); --fg:var(--color-ink);
  --muted:color-mix(in srgb, var(--color-ink) 58%, var(--color-bone));
  --line:color-mix(in srgb, var(--color-ink) 14%, var(--color-bone));
  --accent:var(--color-moss);
  --chipbg:color-mix(in srgb, var(--color-sage) 30%, var(--color-bone));
  --codebg:color-mix(in srgb, var(--color-sage) 20%, var(--color-bone));
  --quote:color-mix(in srgb, var(--color-sage) 16%, var(--color-bone));
  --navbg:color-mix(in srgb, var(--color-sage) 12%, var(--color-bone));
  --th:color-mix(in srgb, var(--color-sage) 24%, var(--color-bone));
}
@media (prefers-color-scheme: dark){
  :root{
    /* Derived from the same five: Ink ground, Deep-Forest surfaces, Bone text, Moss accent. */
    --color-background:var(--color-ink); --color-text:var(--color-bone);
    --bg:var(--color-ink); --fg:var(--color-bone);
    --muted:color-mix(in srgb, var(--color-bone) 56%, var(--color-ink));
    --line:color-mix(in srgb, var(--color-bone) 16%, var(--color-ink));
    --accent:color-mix(in srgb, var(--color-moss) 72%, var(--color-bone));
    --chipbg:color-mix(in srgb, var(--color-deep-forest) 60%, var(--color-ink));
    --codebg:color-mix(in srgb, var(--color-bone) 6%, var(--color-ink));
    --quote:color-mix(in srgb, var(--color-deep-forest) 35%, var(--color-ink));
    --navbg:color-mix(in srgb, var(--color-deep-forest) 22%, var(--color-ink));
    --th:color-mix(in srgb, var(--color-deep-forest) 45%, var(--color-ink));
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--bg); color:var(--fg);
  font-family:var(--font-text);
  font-size:18px; line-height:1.65;
  display:flex;
}
h1,h2,h3{font-family:var(--font-display)}
nav{
  width:300px; min-width:300px; height:100vh; position:sticky; top:0; overflow-y:auto;
  background:var(--navbg); border-right:1px solid var(--line); padding:1.2rem .9rem 3rem;
}
nav .title{font-weight:700; font-size:1.02rem; margin:0 0 .15rem .35rem}
nav .sub{font-size:.74rem; color:var(--muted); margin:0 0 1rem .35rem}
nav ol{list-style:none; margin:0; padding:0}
nav li{margin:.1rem 0}
nav a{display:block; color:var(--fg); text-decoration:none; padding:.28rem .45rem; border-radius:6px; font-size:.86rem}
nav a:hover{background:var(--chipbg)}
nav .nchip{
  display:inline-block; min-width:2.1rem; text-align:center; margin-right:.5rem;
  background:var(--chipbg); color:var(--muted); border-radius:5px;
  font-family:var(--font-code); font-size:.66rem; font-weight:600; letter-spacing:.04em;
  padding:.08rem .3rem; vertical-align:1px;
}
nav li.nav-adr a{font-size:.79rem; color:var(--muted)}
nav li ul{list-style:none; margin:0 0 .3rem 0; padding-left:2.75rem}
nav li ul a{font-size:.76rem; color:var(--muted); padding:.12rem .45rem}
nav .group{font-size:.68rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin:1.1rem 0 .3rem .45rem}
main{flex:1; min-width:0; padding:2.2rem 3rem 6rem; max-width:1000px}
.banner{font-size:.8rem; color:var(--muted); border:1px solid var(--line); border-radius:8px; padding:.6rem .9rem; margin-bottom:1rem}
section.doc{border-top:3px solid var(--line); margin-top:3.2rem; padding-top:1.4rem}
section.doc:first-of-type{border-top:none; margin-top:0; padding-top:0}
.chip{
  display:inline-block; background:var(--chipbg); color:var(--muted);
  font-family:var(--font-code); font-weight:600; text-transform:uppercase;
  font-size:.7rem; letter-spacing:.08em; border-radius:6px; padding:.18rem .55rem; margin-bottom:.4rem;
}
h1{font-size:1.7rem; line-height:1.25; margin:.2rem 0 1rem; letter-spacing:-.015em}
h2{font-size:1.22rem; margin:2.2rem 0 .7rem; letter-spacing:-.01em; padding-top:.3rem}
h3{font-size:1.02rem; margin:1.6rem 0 .5rem}
p{margin:.7rem 0}
a{color:var(--accent)}
blockquote{
  margin:1rem 0; padding:.65rem 1rem; background:var(--quote);
  border-left:3px solid var(--accent); border-radius:0 8px 8px 0; color:var(--muted); font-size:.92rem;
}
blockquote p{margin:.25rem 0}
code{
  font-family:var(--font-code); font-size:.84em;
  background:var(--codebg); border-radius:4px; padding:.1em .35em;
}
pre{
  background:var(--codebg); border:1px solid var(--line); border-radius:8px;
  padding: .9rem 1rem; overflow-x:auto; line-height:1.45; font-size:.8rem;
}
pre code{background:none; padding:0; font-size:1em}
.tw{overflow-x:auto; margin:1rem 0; border:1px solid var(--line); border-radius:8px}
table{border-collapse:collapse; width:100%; font-size:.86rem; line-height:1.5}
th,td{padding:.5rem .7rem; text-align:left; vertical-align:top; border-bottom:1px solid var(--line)}
th{background:var(--th); font-size:.78rem; letter-spacing:.02em; position:sticky; top:0}
tr:last-child td{border-bottom:none}
td:first-child, th:first-child{white-space:nowrap}
ul,ol{padding-left:1.4rem}
li{margin:.25rem 0}
hr{border:none; border-top:1px solid var(--line); margin:2rem 0}
strong{font-weight:650}
@media (max-width: 900px){
  body{flex-direction:column}
  nav{position:static; width:auto; height:auto; min-width:0; border-right:none; border-bottom:1px solid var(--line)}
  main{padding:1.4rem 1.2rem 4rem}
}
@media print{ nav{display:none} main{max-width:none; padding:0} }
pre.mermaid{background:none; border:none; padding:0; overflow-x:auto; text-align:center; line-height:1.4}
pre.mermaid svg{max-width:100%; height:auto}
`;

const firstAdrIdx = navEntries.findIndex((d) => d.adr);
const navHtml = (items) => items.map((d) => {
  const subs = d.adr || !d.subs.length ? '' :
    `<ul>${d.subs.map((s) => `<li><a href="#${s.id}">${s.label}</a></li>`).join('')}</ul>`;
  return `<li class="${d.adr ? 'nav-adr' : 'nav-doc'}"><a href="#${d.id}"><span class="nchip">${d.chip}</span>${d.nav}</a>${subs}</li>`;
}).join('\n');

// Inline the mermaid browser bundle + an initializer, but only when the corpus actually
// contains mermaid blocks — the bundle is ~3.3 MB, so a diagram-free build stays ~200 KB.
// Theme follows prefers-color-scheme so diagrams match the page's light/dark palette.
function mermaidScript() {
  if (!mermaidCount) return '';
  const bundlePath = mermaidBundlePath();
  if (!bundlePath) {
    console.warn(`warning: ${mermaidCount} mermaid block(s) found but the mermaid bundle was not resolvable ` +
      `(mermaid/dist/mermaid.min.js) — diagrams will render as plain text. Run \`yarn install\` or set NODE_PATH.`);
    return '';
  }
  const lib = readFileSync(bundlePath, 'utf8');
  return `<script>${lib}</script>
<script>
(function () {
  var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  mermaid.initialize({ startOnLoad: false, theme: dark ? 'dark' : 'default', securityLevel: 'strict' });
  mermaid.run({ querySelector: 'pre.mermaid' });
})();
</script>`;
}
const mermaidTag = mermaidScript();

const page = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eden Architecture — review build</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<!-- Eden's three locked families (tokens.json). Online viewing gets exact fonts;
     offline falls back to the per-role stacks in :root — the self-contained-file compromise. -->
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,900&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>${css}</style>
</head>
<body>
<nav>
  <p class="title">Eden Architecture</p>
  <p class="sub">review build · generated ${GENERATED} from docs/architecture</p>
  <div class="group">Documents</div>
  <ol>${navHtml(navEntries.slice(0, firstAdrIdx))}</ol>
  <div class="group">Decision records</div>
  <ol>${navHtml(navEntries.slice(firstAdrIdx))}</ol>
</nav>
<main>
<div class="banner">Generated from the markdown in <code>docs/architecture/</code> — the markdown stays the source of truth; this file is a reading copy. Legend: ✅ verified · 🔶 hypothesis · ⚠️ corrected · 🧩 design choice.</div>
${sections.join('\n')}
</main>
${mermaidTag}
</body>
</html>`;

writeFileSync(OUT, page);
console.log(`wrote ${OUT} (${(page.length / 1024).toFixed(0)} KB)`);
