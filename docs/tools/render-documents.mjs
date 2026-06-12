// Renders a project's document set into a single self-contained HTML reading copy.
// Usage: node docs/tools/render-documents.mjs <documents-dir> [--out <file>]
//        (default out: <documents-dir>/documents.html)
// Requires `marked` (a devDependency — `yarn install` provides it; or set NODE_PATH,
// e.g. NODE_PATH=/tmp/eden-render/node_modules in this environment).
//
// Source of truth is the validator: this script never re-implements the projection.
// It shells out to `documentvalidator project|links|validate` and renders their output.
// The .md/.yaml files are the authoring format; this file is a reading copy (regenerate).

import { readFileSync, writeFileSync, existsSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';

const require = createRequire(import.meta.url);
let marked;
try {
  ({ marked } = require('marked'));
} catch {
  console.error('marked not found — run `yarn install` (it is a devDependency), or set NODE_PATH.');
  process.exit(1);
}
marked.use({ gfm: true });

// Locate the self-contained mermaid browser bundle (mermaid.min.js, ~3.3 MB) so it can be
// inlined and keep the HTML offline. Resolved via the same require used for marked.
function mermaidBundlePath() {
  try {
    return require.resolve('mermaid/dist/mermaid.min.js');
  } catch {
    return null;
  }
}

// ── arguments ────────────────────────────────────────────────────────────────
const argv = process.argv.slice(2);
let docsDir = null;
let outFile = null;
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--out') { outFile = argv[++i]; continue; }
  if (!docsDir) { docsDir = argv[i]; continue; }
  console.error(`unexpected argument: ${argv[i]}`);
  process.exit(2);
}
if (!docsDir) {
  console.error('Usage: node docs/tools/render-documents.mjs <documents-dir> [--out <file>]');
  process.exit(2);
}
docsDir = resolve(docsDir);
if (!existsSync(docsDir) || !statSync(docsDir).isDirectory()) {
  console.error(`not a directory: ${docsDir}`);
  process.exit(2);
}
outFile = outFile ? resolve(outFile) : `${docsDir}/documents.html`;

const VALIDATOR_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', 'tools', 'documentvalidator');
const GENERATED = new Date().toISOString().slice(0, 10);

// ── invoke the validator (single source of truth) ────────────────────────────
function runValidator(verb, extraArgs, { allowFailure = false } = {}) {
  try {
    return execFileSync('go', ['run', './cmd/documentvalidator', verb, docsDir, ...extraArgs],
      { cwd: VALIDATOR_DIR, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (e) {
    // validate exits 1 on violations — its stdout still carries the JSON we want.
    if (allowFailure && e.stdout) return e.stdout;
    console.error(`documentvalidator ${verb} failed: ${e.stderr || e.message}`);
    process.exit(1);
  }
}

const projectionsRaw = runValidator('project', []);
const documents = projectionsRaw.split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
const edges = JSON.parse(runValidator('links', ['--json']));
const report = JSON.parse(runValidator('validate', ['--json'], { allowFailure: true }));

const projectName = documents.find((d) => d.meta?.project)?.meta.project || 'project';

// ── derive: tiers, item index, backlinks ─────────────────────────────────────
// Tier ordering follows doc 11 §2 (Product → Architecture → Implementation).
const TIERS = [
  { key: 'product', label: 'Product', types: ['product-charter', 'requirements', 'user-workflows', 'design-brief'] },
  { key: 'architecture', label: 'Architecture', types: ['domain-model', 'system-design', 'service-contracts', 'architecture-decision'] },
  { key: 'implementation', label: 'Implementation', types: ['implementation-plan', 'specification'] },
];
const tierOf = (type) => TIERS.find((t) => t.types.includes(type))?.key || 'implementation';
const tierRank = (type) => { const i = TIERS.findIndex((t) => t.types.includes(type)); return i < 0 ? TIERS.length : i; };
const typeRank = (type) => { const t = TIERS.find((x) => x.types.includes(type)); const i = t ? t.types.indexOf(type) : -1; return i < 0 ? 99 : i; };

documents.sort((a, b) =>
  tierRank(a.meta.type) - tierRank(b.meta.type) ||
  typeRank(a.meta.type) - typeRank(b.meta.type) ||
  a.meta.id.localeCompare(b.meta.id));

// data arrays that carry item-id'd records, by document type → array key
const ITEM_ARRAYS = {
  'product-charter': ['personas'],
  'requirements': ['items'],
  'user-workflows': ['items'],
  'domain-model': ['entities', 'invariants'],
  'system-design': ['components'],
  'service-contracts': ['contracts'],
  'implementation-plan': ['packages'],
};

// Index every item id → {documentId, type, item}. Also index document ids themselves
// (adr-0001, spec-0001, design-brief …) so links to whole documents resolve too.
const itemIndex = new Map();   // id → { docId, label }
for (const d of documents) {
  itemIndex.set(d.meta.id, { docId: d.meta.id, label: d.meta.id });
  const keys = ITEM_ARRAYS[d.meta.type] || [];
  for (const k of keys) {
    for (const it of (d.data?.[k] || [])) {
      if (it && it.id) itemIndex.set(it.id, { docId: d.meta.id, label: it.name || it.id });
    }
  }
}

// Backlinks: for each target id, the set of {from, type} edges pointing at it.
const backlinks = new Map();   // targetId → [{ from, type }]
for (const e of edges) {
  if (!backlinks.has(e.to)) backlinks.set(e.to, []);
  backlinks.get(e.to).push({ from: e.from, type: e.type });
}
const REVERSE_VERB = {
  realizes: 'realized by', refines: 'refined by', verifies: 'verified by',
  supersedes: 'superseded by', informs: 'informed',
};

// ── html helpers ─────────────────────────────────────────────────────────────
const esc = (s) => String(s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

const anchorId = (id) => `item-${id}`;
const docAnchorId = (id) => `doc-${id}`;

// Resolve an id to a hyperlink targeting its item anchor (or document anchor),
// or a plain code span if it is external (artifact://…, path://…) or unresolved.
function idLink(id) {
  const known = itemIndex.get(id);
  if (known) {
    const target = id === known.docId ? docAnchorId(id) : anchorId(id);
    return `<a class="ref" href="#${target}"><code>${esc(id)}</code></a>`;
  }
  return `<code class="ref-ext">${esc(id)}</code>`;
}

const STATUS_ORDER = ['draft', 'review', 'approved', 'superseded'];
const statusChip = (status) =>
  `<span class="chip status-${esc(status)}">${esc(status)}</span>`;

// marked renders a ```mermaid fence as <pre><code class="language-mermaid">…</code></pre>;
// mermaid's browser API expects <pre class="mermaid">…</pre>. Rewrite those blocks (and only
// those), decoding the entities marked introduced, and count them so the ~3.3 MB bundle is
// only inlined when at least one diagram is present.
const MERMAID_BLOCK_RE = /<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g;
let mermaidCount = 0;
function transformMermaid(html) {
  return html.replace(MERMAID_BLOCK_RE, (_, body) => {
    mermaidCount++;
    const code = body
      .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
    return `<pre class="mermaid">${code}</pre>`;
  });
}

// Markdown → HTML, with the same table-wrapper and mermaid treatment as render-html.mjs.
function md(src) {
  if (src == null || src === '') return '';
  let html = marked.parse(String(src));
  html = transformMermaid(html);
  return html.replace(/<table>/g, '<div class="tw"><table>').replace(/<\/table>/g, '</table></div>');
}

// Render the typed links block of any record/meta as resolved anchors.
function linksBlock(links) {
  if (!links) return '';
  const parts = [];
  for (const [type, val] of Object.entries(links)) {
    if (val == null) continue;
    const arr = Array.isArray(val) ? val : [val];
    if (!arr.length) continue;
    parts.push(`<span class="lk"><span class="lk-t">${esc(type)}</span> ${arr.map(idLink).join(' ')}</span>`);
  }
  return parts.length ? `<div class="links">${parts.join('')}</div>` : '';
}

// Backlinks for an id (derived; never authored).
function backlinkBlock(id) {
  const bl = backlinks.get(id);
  if (!bl || !bl.length) return '';
  const byType = new Map();
  for (const { from, type } of bl) {
    if (!byType.has(type)) byType.set(type, []);
    byType.get(type).push(from);
  }
  const parts = [];
  for (const [type, froms] of byType) {
    parts.push(`<span class="lk back"><span class="lk-t">${esc(REVERSE_VERB[type] || type)}</span> ${froms.map(idLink).join(' ')}</span>`);
  }
  return `<div class="links backlinks">${parts.join('')}</div>`;
}

// A scalar cell value. Objects/arrays get compacted; ids are linked when they look
// like item references (PREFIX-NNNN) or are known.
const ID_RE = /^[A-Z]{2,4}-\d{4}$/;
function cell(v) {
  if (v == null) return '<span class="muted">—</span>';
  if (Array.isArray(v)) {
    if (!v.length) return '<span class="muted">—</span>';
    if (v.every((x) => x == null || typeof x !== 'object')) {
      return v.map((x) => ID_RE.test(String(x)) ? idLink(String(x)) : esc(x)).join(', ');
    }
    return `<ul class="cl">${v.map((x) => `<li>${cell(x)}</li>`).join('')}</ul>`;
  }
  if (typeof v === 'object') return defList(v);
  const s = String(v);
  if (ID_RE.test(s)) return idLink(s);
  // Multi-line prose → render as markdown so EARS statements / descriptions read well.
  if (s.includes('\n') || /[*_`#-]/.test(s)) return md(s);
  return esc(s);
}

// Nested object → definition list (doc 11 §5 / task spec).
function defList(obj) {
  const rows = Object.entries(obj).map(([k, v]) => {
    if (k === 'links') return `<dt>${esc(k)}</dt><dd>${linksBlock(v) || '<span class="muted">—</span>'}</dd>`;
    return `<dt>${esc(k)}</dt><dd>${cell(v)}</dd>`;
  });
  return `<dl class="dl">${rows.join('')}</dl>`;
}

// Array-of-objects → table. Item-id'd rows get an anchor + a backlinks line.
function recordsTable(arr, { itemized = false } = {}) {
  // union of keys, stable order, links last
  const keys = [];
  for (const o of arr) for (const k of Object.keys(o)) if (!keys.includes(k)) keys.push(k);
  const ordered = keys.filter((k) => k !== 'links').concat(keys.includes('links') ? ['links'] : []);
  const head = `<tr>${ordered.map((k) => `<th>${esc(k)}</th>`).join('')}</tr>`;
  const body = arr.map((o) => {
    const idAttr = itemized && o.id ? ` id="${anchorId(o.id)}"` : '';
    const tds = ordered.map((k) => {
      if (k === 'links') return `<td>${linksBlock(o.links) || '<span class="muted">—</span>'}</td>`;
      if (k === 'id' && o.id) {
        return `<td class="idcell"><code>${esc(o.id)}</code>${itemized ? backlinkBlock(o.id) : ''}</td>`;
      }
      return `<td>${cell(o[k])}</td>`;
    });
    return `<tr${idAttr}>${tds.join('')}</tr>`;
  }).join('');
  return `<div class="tw"><table>${head}${body}</table></div>`;
}

// Render a document's `data` block: item arrays as itemized tables, other arrays as
// plain tables, scalar/object leftovers as a definition list.
function renderData(d) {
  const data = d.data;
  if (!data || !Object.keys(data).length) return '';
  const itemKeys = new Set(ITEM_ARRAYS[d.meta.type] || []);
  const out = [];
  const leftovers = {};
  for (const [k, v] of Object.entries(data)) {
    if (Array.isArray(v) && v.length && v.every((x) => x && typeof x === 'object')) {
      out.push(`<h3 class="dkey">${esc(k)}</h3>${recordsTable(v, { itemized: itemKeys.has(k) })}`);
    } else if (v && typeof v === 'object' && !Array.isArray(v)) {
      out.push(`<h3 class="dkey">${esc(k)}</h3>${defList(v)}`);
    } else {
      leftovers[k] = v;
    }
  }
  if (Object.keys(leftovers).length) out.unshift(defList(leftovers));
  return out.join('\n');
}

// Markdown sections (narrative docs) with stable heading ids.
function renderSections(d) {
  const secs = d.sections;
  if (!secs || !Object.keys(secs).length) return '';
  return Object.entries(secs).map(([k, v]) =>
    `<div class="section"><h3 id="${docAnchorId(d.meta.id)}--${esc(k)}" class="skey">${esc(k)}</h3>${md(v)}</div>`
  ).join('\n');
}

// ── per-document section ─────────────────────────────────────────────────────
function authorLabel(a) {
  if (a.human) return `human: ${esc(a.human)}`;
  if (a.run) return `run: ${esc(a.run)}`;
  return esc(JSON.stringify(a));
}

function metaCard(m) {
  const rows = [
    ['id', `<code>${esc(m.id)}</code>`],
    ['type', esc(m.type)],
    ['version', `v${esc(m.version)}`],
    ['status', statusChip(m.status)],
    ['schema', esc(m.schema_version)],
    ['updated', esc(m.updated)],
    ['authors', (m.authors || []).map(authorLabel).join(' · ') || '<span class="muted">—</span>'],
  ];
  const linkRow = linksBlock(m.links);
  return `<div class="meta-card">
  <dl class="meta-dl">${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>
  ${linkRow ? `<div class="meta-links"><span class="meta-links-t">links</span>${linkRow}</div>` : ''}
</div>`;
}

const TYPE_LABEL = {
  'product-charter': 'Product charter', 'requirements': 'Requirements',
  'user-workflows': 'User workflows', 'design-brief': 'Design brief',
  'domain-model': 'Domain model', 'system-design': 'System design',
  'service-contracts': 'Service contracts', 'architecture-decision': 'Architecture decision',
  'implementation-plan': 'Implementation plan', 'specification': 'Specification',
};
const docTitle = (m) => `${TYPE_LABEL[m.type] || m.type} <span class="dtitle-id">${esc(m.id)}</span>`;

const docSections = documents.map((d) => {
  const m = d.meta;
  return `<section id="${docAnchorId(m.id)}" class="doc" data-tier="${tierOf(m.type)}">
  <div class="chip tier-${tierOf(m.type)}">${esc(tierOf(m.type))}</div>
  <h2>${docTitle(m)} ${statusChip(m.status)}</h2>
  ${metaCard(m)}
  ${renderData(d)}
  ${renderSections(d)}
</section>`;
}).join('\n');

// ── overview: status counts, coverage, diagnostics, edges ────────────────────
const statusCounts = {};
for (const d of documents) statusCounts[d.meta.status] = (statusCounts[d.meta.status] || 0) + 1;
const statusCountHtml = STATUS_ORDER
  .filter((s) => statusCounts[s])
  .map((s) => `${statusChip(s)} <strong>${statusCounts[s]}</strong>`)
  .join('&nbsp;&nbsp;');

function diagTable(rows, emptyMsg) {
  if (!rows.length) return `<p class="ok-line">✅ ${emptyMsg}</p>`;
  const body = rows.map((r) => `<tr>
    <td>${r.rule ? `<code>${esc(r.rule)}</code>` : '<span class="muted">schema</span>'}</td>
    <td>${r.documentId ? idLink(r.documentId) : `<code>${esc(r.file)}</code>`}</td>
    <td>${esc(r.message)}</td></tr>`).join('');
  return `<div class="tw"><table><tr><th>rule</th><th>where</th><th>message</th></tr>${body}</table></div>`;
}

const edgeTypes = [...new Set(edges.map((e) => e.type))].sort();
const edgesByType = edgeTypes.map((t) => {
  const es = edges.filter((e) => e.type === t);
  const rows = es.map((e) => `<tr><td>${idLink(e.from)}</td><td class="arrow">→</td><td>${idLink(e.to)}</td></tr>`).join('');
  return `<div class="edgegroup"><h4>${esc(t)} <span class="muted">· ${es.length}</span></h4><div class="tw"><table>${rows}</table></div></div>`;
}).join('');

const overview = `<section id="overview" class="doc overview">
  <div class="chip">Overview</div>
  <h2>${esc(projectName)} — document set</h2>
  <p class="lead">${documents.length} documents · ${edges.length} link edges · validation ${report.ok ? '<span class="ok-line">passing ✅</span>' : '<span class="bad-line">violations present ⚠️</span>'}</p>
  <div class="counts">${statusCountHtml}</div>

  <h3>Validation diagnostics</h3>
  ${diagTable(report.violations || [], 'No shape or traceability (T1–T5) violations.')}

  <h3>T6 coverage</h3>
  ${diagTable(report.coverage || [], 'Every P1 requirement reaches a specification.')}

  <h3>Link edges <span class="muted">· ${edges.length} total</span></h3>
  <div class="edges">${edgesByType}</div>
</section>`;

// ── sidebar ──────────────────────────────────────────────────────────────────
const sidebar = TIERS.map((t) => {
  const docs = documents.filter((d) => tierOf(d.meta.type) === t.key);
  if (!docs.length) return '';
  const lis = docs.map((d) => {
    const m = d.meta;
    return `<li><a href="#${docAnchorId(m.id)}">
      <span class="nav-row"><span class="nav-label">${TYPE_LABEL[m.type] || m.type}</span>
      <span class="nav-meta">${statusChip(m.status)}<span class="nav-v">v${esc(m.version)}</span></span></span>
      <span class="nav-id">${esc(m.id)}</span></a></li>`;
  }).join('');
  return `<div class="group">${esc(t.label)}</div><ol>${lis}</ol>`;
}).join('');

// ── styles (extends the render-html.mjs palette; adds status/tier chips) ──────
const css = `
:root{
  --bg:#ffffff; --fg:#1d2129; --muted:#5b6472; --line:#e3e6ea; --accent:#2563eb;
  --chipbg:#eef2f7; --codebg:#f5f6f8; --quote:#f7f8fa; --navbg:#fafbfc; --th:#f0f2f5;
  --card:#fafbfc;
  --st-draft:#b45309; --st-draft-bg:#fef3c7; --st-review:#7c3aed; --st-review-bg:#ede9fe;
  --st-approved:#15803d; --st-approved-bg:#dcfce7; --st-superseded:#6b7280; --st-superseded-bg:#f1f3f5;
  --tier-product:#2563eb; --tier-architecture:#0891b2; --tier-implementation:#9333ea;
  --ok:#15803d; --bad:#b91c1c;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#15171b; --fg:#e6e8ec; --muted:#9aa3b0; --line:#2a2e35; --accent:#7aa2ff;
    --chipbg:#23272e; --codebg:#1e2126; --quote:#1b1e23; --navbg:#191c20; --th:#20242a;
    --card:#181b20;
    --st-draft:#fbbf24; --st-draft-bg:#3a2e12; --st-review:#c4b5fd; --st-review-bg:#2a2440;
    --st-approved:#86efac; --st-approved-bg:#13301d; --st-superseded:#9ca3af; --st-superseded-bg:#23272e;
    --tier-product:#7aa2ff; --tier-architecture:#3fc6dc; --tier-implementation:#c084fc;
    --ok:#86efac; --bad:#fca5a5;
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--bg); color:var(--fg);
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;
  font-size:16px; line-height:1.65; display:flex;
}
nav{
  width:300px; min-width:300px; height:100vh; position:sticky; top:0; overflow-y:auto;
  background:var(--navbg); border-right:1px solid var(--line); padding:1.2rem .9rem 3rem;
}
nav .title{font-weight:700; font-size:1.02rem; margin:0 0 .15rem .35rem}
nav .sub{font-size:.74rem; color:var(--muted); margin:0 0 1rem .35rem}
nav ol{list-style:none; margin:0 0 .4rem; padding:0}
nav li{margin:.12rem 0}
nav a{display:block; color:var(--fg); text-decoration:none; padding:.35rem .5rem; border-radius:7px}
nav a:hover{background:var(--chipbg)}
nav .nav-row{display:flex; align-items:center; justify-content:space-between; gap:.4rem}
nav .nav-label{font-size:.86rem; font-weight:600}
nav .nav-meta{display:flex; align-items:center; gap:.3rem; white-space:nowrap}
nav .nav-v{font-size:.68rem; color:var(--muted)}
nav .nav-id{display:block; font-size:.68rem; color:var(--muted); font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace; margin-top:.1rem}
nav .group{font-size:.68rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin:1.1rem 0 .35rem .5rem}
nav .ovlink a{font-weight:600}
main{flex:1; min-width:0; padding:2.2rem 3rem 6rem; max-width:1040px}
.banner{font-size:.8rem; color:var(--muted); border:1px solid var(--line); border-radius:8px; padding:.6rem .9rem; margin-bottom:1.2rem}
section.doc{border-top:3px solid var(--line); margin-top:3rem; padding-top:1.3rem}
section.doc:first-of-type{border-top:none; margin-top:0; padding-top:0}
h1{font-size:1.7rem; line-height:1.25; margin:.2rem 0 1rem; letter-spacing:-.015em}
h2{font-size:1.32rem; margin:.4rem 0 .8rem; letter-spacing:-.01em; display:flex; align-items:center; gap:.55rem; flex-wrap:wrap}
.dtitle-id{font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace; font-size:.72em; color:var(--muted); font-weight:500}
h3{font-size:1.02rem; margin:1.6rem 0 .5rem}
h3.dkey,h3.skey{font-size:.82rem; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:1.5rem 0 .5rem}
h4{font-size:.8rem; margin:1rem 0 .35rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em}
p{margin:.7rem 0}
a{color:var(--accent)}
a.ref{text-decoration:none}
a.ref code{background:var(--chipbg); color:var(--accent); border-radius:4px; padding:.08em .35em; font-size:.84em}
a.ref:hover code{background:var(--accent); color:#fff}
code.ref-ext{background:var(--codebg); color:var(--muted); border-radius:4px; padding:.08em .35em; font-size:.84em}
.lead{color:var(--muted); font-size:.94rem; margin:.3rem 0 .9rem}
.counts{margin:.4rem 0 1.4rem; font-size:.9rem}
.ok-line{color:var(--ok)} .bad-line{color:var(--bad)}
code{font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace; font-size:.84em; background:var(--codebg); border-radius:4px; padding:.1em .35em;}
pre{background:var(--codebg); border:1px solid var(--line); border-radius:8px; padding:.9rem 1rem; overflow-x:auto; line-height:1.45; font-size:.8rem;}
pre code{background:none; padding:0; font-size:1em}
.tw{overflow-x:auto; margin:.7rem 0; border:1px solid var(--line); border-radius:8px}
table{border-collapse:collapse; width:100%; font-size:.85rem; line-height:1.5}
th,td{padding:.5rem .7rem; text-align:left; vertical-align:top; border-bottom:1px solid var(--line)}
th{background:var(--th); font-size:.72rem; letter-spacing:.02em; text-transform:uppercase; color:var(--muted)}
tr:last-child td{border-bottom:none}
td.idcell{white-space:nowrap}
td.arrow,.arrow{color:var(--muted); width:1.5rem; text-align:center}
table p:first-child{margin-top:0} table p:last-child{margin-bottom:0}
ul,ol{padding-left:1.4rem} li{margin:.22rem 0}
ul.cl{margin:0; padding-left:1.1rem} ul.cl li{margin:.1rem 0}
hr{border:none; border-top:1px solid var(--line); margin:2rem 0}
strong{font-weight:650}
.muted{color:var(--muted)}
.chip{display:inline-block; background:var(--chipbg); color:var(--muted); font-weight:700; font-size:.66rem; letter-spacing:.05em; border-radius:6px; padding:.18rem .55rem; text-transform:uppercase}
.chip.tier-product{color:var(--tier-product)} .chip.tier-architecture{color:var(--tier-architecture)} .chip.tier-implementation{color:var(--tier-implementation)}
.chip.status-draft{background:var(--st-draft-bg); color:var(--st-draft)}
.chip.status-review{background:var(--st-review-bg); color:var(--st-review)}
.chip.status-approved{background:var(--st-approved-bg); color:var(--st-approved)}
.chip.status-superseded{background:var(--st-superseded-bg); color:var(--st-superseded)}
.meta-card{background:var(--card); border:1px solid var(--line); border-radius:10px; padding:.9rem 1rem; margin:.6rem 0 1.1rem}
.meta-dl{display:flex; flex-wrap:wrap; gap:.4rem 1.6rem; margin:0}
.meta-dl div{min-width:0}
.meta-dl dt{font-size:.66rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted)}
.meta-dl dd{margin:.05rem 0 0; font-size:.9rem}
.meta-links{margin-top:.7rem; padding-top:.7rem; border-top:1px solid var(--line)}
.meta-links-t{font-size:.66rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-right:.5rem}
.links{display:flex; flex-wrap:wrap; gap:.4rem .8rem; margin:.15rem 0}
.lk{font-size:.84rem}
.lk-t{font-size:.66rem; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); margin-right:.3rem}
.backlinks .lk-t{color:var(--accent)}
.idcell .links{margin-top:.3rem}
dl.dl{margin:0} dl.dl dt{font-size:.74rem; font-weight:650; color:var(--muted); margin-top:.4rem} dl.dl dt:first-child{margin-top:0} dl.dl dd{margin:.05rem 0 0}
.section{margin:.4rem 0}
.edges{display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:1rem}
.edgegroup table{font-size:.8rem}
@media (max-width: 900px){
  body{flex-direction:column}
  nav{position:static; width:auto; height:auto; min-width:0; border-right:none; border-bottom:1px solid var(--line)}
  main{padding:1.4rem 1.2rem 4rem}
  .edges{grid-template-columns:1fr}
}
@media print{ nav{display:none} main{max-width:none; padding:0} }
pre.mermaid{background:none; border:none; padding:0; overflow-x:auto; text-align:center; line-height:1.4}
pre.mermaid svg{max-width:100%; height:auto}
`;

// Inline the mermaid bundle + initializer only when the document set contains mermaid blocks
// (the bundle is ~3.3 MB; a diagram-free build stays small). Theme follows prefers-color-scheme.
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
<title>${esc(projectName)} — document set</title>
<style>${css}</style>
</head>
<body>
<nav>
  <p class="title">${esc(projectName)}</p>
  <p class="sub">document set · generated ${GENERATED}</p>
  <ol class="ovlink"><li><a href="#overview"><span class="nav-row"><span class="nav-label">Overview</span></span></a></li></ol>
  ${sidebar}
</nav>
<main>
<div class="banner">Generated by <code>render-documents.mjs</code> from the <code>documentvalidator</code> projection — the <code>.md</code>/<code>.yaml</code> files stay the source of truth; this is a reading copy. Status: draft · review · approved · superseded. Backlinks ("realized by …") are derived from the link graph, never authored.</div>
${overview}
${docSections}
</main>
${mermaidTag}
</body>
</html>`;

writeFileSync(outFile, page);
console.log(`wrote ${outFile} (${(page.length / 1024).toFixed(0)} KB) — ${documents.length} documents, ${edges.length} edges, validation ${report.ok ? 'OK' : 'with violations'}`);
