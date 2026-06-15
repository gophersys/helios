// libs/typescript/_ctl/cohesion-scan.mjs
//
// The TypeScript cohesion / dead-export detector (ADR-0024 Stage-3 ENFORCE — the analog of the Go
// pipeline's `_cohesion_scan` + the two cross-lib duplication detectors in libs/go/_ctl/lib.sh).
// The TS track previously had NO cohesion dimension at all (audit: "a TS lib can re-derive another
// TS lib's entire generator and stay phase-gate-all GREEN"; "a fully dead exported type cluster
// sails through phase-gate-all green"). This closes both gaps with a TS-aware scan over the whole
// TypeScript workspace, using the TypeScript compiler API (already a workspace devDep — no new tool).
//
// Two FAIL conditions (one concept, one home — 10 §9):
//
//   (A) DEAD EXPORT. An exported symbol declared in a NON-index module that is reachable from
//       NOWHERE: it is neither re-exported by its own lib's public barrel (src/index.ts) NOR
//       imported by any other module across the TS libs. This is the "scale dead-end" / dead-DTCG
//       class — an exported declaration nothing produces or consumes. (A symbol that the barrel
//       re-exports IS part of the public API and is exempt; the barrel is the lib's published
//       surface, frozen by .apibaseline.)
//
//   (B) CROSS-LIB MATH DUPLICATION. An exported math constant or function in a downstream @eden lib
//       whose IDENTIFIER collides with one already exported by a FOUNDATION lib (a lib that other
//       libs depend on — here @eden/scale), UNLESS the downstream lib imports that identifier FROM
//       the foundation lib. This is the "theme reimplements scale's generator" class: the modular-
//       scale generator + INTERVAL_RATIO live once in @eden/scale; theme CITES, never re-derives.
//       A re-exported citation (`export { stepAt } from "@eden/scale"`) or a local binding imported
//       from the foundation is fine — re-deriving the same-named symbol locally is the FAIL.
//
// Usage:  node _ctl/cohesion-scan.mjs [--lib <slug>]
//   --lib <slug>  restrict the FAIL surface to findings touching <slug> (the per-lib gate); the
//                 scan still reads ALL libs (importer counting is necessarily whole-workspace), but
//                 only findings whose owning module is in <slug> fail the process. Omit to scan all.
//
// Exit 0 = clean, 1 = at least one cohesion violation (printed with file:line and the fix pointer).

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import ts from 'typescript';

const WORKSPACE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// ── CLI ───────────────────────────────────────────────────────────────────────────────────────
const argv = process.argv.slice(2);
let onlyLib = null;
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--lib') onlyLib = argv[++i];
}

// ── lib discovery: a TS lib is a workspace dir with a ctl.sh + a src/ ───────────────────────────
function discoverLibs() {
  return fs
    .readdirSync(WORKSPACE, { withFileTypes: true })
    .filter((d) => d.isDirectory() && !d.name.startsWith('.') && d.name !== 'node_modules' && d.name !== '_ctl')
    .filter((d) => fs.existsSync(path.join(WORKSPACE, d.name, 'ctl.sh')) && fs.existsSync(path.join(WORKSPACE, d.name, 'src')))
    .map((d) => {
      const dir = path.join(WORKSPACE, d.name);
      let scope = '@eden';
      let pkgName = `@eden/${d.name}`;
      let dependencies = {};
      try {
        const pkg = JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf-8'));
        if (pkg.name) {
          pkgName = pkg.name;
          scope = pkg.name.split('/')[0];
        }
        dependencies = { ...(pkg.dependencies || {}), ...(pkg.peerDependencies || {}) };
      } catch {
        /* a lib without a package.json keeps the @eden/<slug> default */
      }
      return { slug: d.name, dir, pkgName, scope, dependencies };
    });
}

// ── source-file collection (non-test *.ts/*.svelte under src) ───────────────────────────────────
function sourceFiles(libDir) {
  const out = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (
        /\.(ts|svelte)$/.test(entry.name) &&
        !/\.(test|property\.test|design\.test|spec)\.ts$/.test(entry.name)
      ) {
        out.push(full);
      }
    }
  };
  walk(path.join(libDir, 'src'));
  return out;
}

function parse(file) {
  const text = fs.readFileSync(file, 'utf-8');
  return ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
}

// Collect the exported declaration NAMES of a source file, classified.
// Returns: { names: Map<name,{line, kind}>, reExportsFrom: Map<name, moduleSpecifier>,
//            starReExports: string[], importsByName: Map<name, moduleSpecifier> }
function analyzeFile(file) {
  const sf = parse(file);
  const names = new Map(); // locally-declared exported symbol -> {line, kind, isMathConst, isMathFn}
  const reExportsFrom = new Map(); // name -> source module (export { x } from 'mod')
  const starReExports = []; // 'mod' from export * from 'mod'
  const importsByName = new Map(); // local binding name -> source module
  const importsOriginalByModule = new Map(); // ORIGINAL imported name -> source module (alias-blind:
  //   `import { DEFAULT_TYPE_RATIO as X } from '@eden/scale'` records DEFAULT_TYPE_RATIO -> @eden/scale,
  //   so an aliased citation of a foundation symbol is recognized regardless of the local binding.
  const importedIdentifiers = new Set(); // every identifier referenced as an import binding

  const lineOf = (node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;

  const looksMathConst = (decl) => {
    // an exported `const NAME = <number|expr>` that is a numeric/record-of-number seed or table.
    if (!decl.initializer) return false;
    const init = decl.initializer;
    if (ts.isNumericLiteral(init)) return true;
    // Object.freeze({...}) / a record literal of numbers (a ratio table)
    const txt = init.getText(sf);
    return /Object\.freeze\(|\bRecord<|=>\s*[\d.]/.test(txt) || /^[\d.]/.test(txt);
  };

  ts.forEachChild(sf, (node) => {
    // import declarations
    if (ts.isImportDeclaration(node) && node.importClause) {
      const mod = node.moduleSpecifier.getText(sf).replace(/^['"]|['"]$/g, '');
      const clause = node.importClause;
      if (clause.name) {
        importsByName.set(clause.name.text, mod);
        importedIdentifiers.add(clause.name.text);
      }
      if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
        for (const el of clause.namedBindings.elements) {
          const local = el.name.text;
          const orig = el.propertyName ? el.propertyName.text : el.name.text;
          importsByName.set(local, mod);
          importsOriginalByModule.set(orig, mod);
          importedIdentifiers.add(local);
          importedIdentifiers.add(orig);
        }
      }
      return;
    }
    // export { x } from 'mod'  /  export * from 'mod'
    if (ts.isExportDeclaration(node)) {
      if (node.moduleSpecifier) {
        const mod = node.moduleSpecifier.getText(sf).replace(/^['"]|['"]$/g, '');
        if (node.exportClause && ts.isNamedExports(node.exportClause)) {
          for (const el of node.exportClause.elements) {
            const exportedName = el.name.text;
            reExportsFrom.set(exportedName, mod);
          }
        } else {
          starReExports.push(mod);
        }
      } else if (node.exportClause && ts.isNamedExports(node.exportClause)) {
        // export { local } — re-export of a local binding
        for (const el of node.exportClause.elements) {
          names.set(el.name.text, { line: lineOf(node), kind: 'export-local' });
        }
      }
      return;
    }
    // exported declarations: const/function/class/interface/type/enum
    const hasExport =
      node.modifiers && node.modifiers.some((m) => m.kind === ts.SyntaxKind.ExportKeyword);
    if (!hasExport) return;
    if (ts.isVariableStatement(node)) {
      for (const decl of node.declarationList.declarations) {
        if (ts.isIdentifier(decl.name)) {
          names.set(decl.name.text, {
            line: lineOf(decl),
            kind: 'const',
            isMathConst: looksMathConst(decl),
          });
        }
      }
    } else if (
      ts.isFunctionDeclaration(node) ||
      ts.isClassDeclaration(node) ||
      ts.isInterfaceDeclaration(node) ||
      ts.isTypeAliasDeclaration(node) ||
      ts.isEnumDeclaration(node)
    ) {
      if (node.name) {
        const kind = ts.isFunctionDeclaration(node)
          ? 'function'
          : ts.isClassDeclaration(node)
            ? 'class'
            : ts.isInterfaceDeclaration(node)
              ? 'interface'
              : ts.isTypeAliasDeclaration(node)
                ? 'type'
                : 'enum';
        names.set(node.name.text, { line: lineOf(node), kind });
      }
    }
  });

  // Count identifier *references* (whole-file) so we can tell a re-exported barrel symbol from a
  // genuinely-referenced one for the importer scan.
  const referenced = new Set();
  const visit = (node) => {
    if (ts.isIdentifier(node)) referenced.add(node.text);
    ts.forEachChild(node, visit);
  };
  visit(sf);

  return {
    file,
    names,
    reExportsFrom,
    starReExports,
    importsByName,
    importsOriginalByModule,
    importedIdentifiers,
    referenced,
  };
}

// ── main scan ───────────────────────────────────────────────────────────────────────────────────
const libs = discoverLibs();
const bySlug = new Map(libs.map((l) => [l.slug, l]));
const pkgToSlug = new Map(libs.map((l) => [l.pkgName, l.slug]));

// Build per-lib file analyses.
const analyses = new Map(); // slug -> { files: [analysis], indexExports: Set, indexReExports: Map }
for (const lib of libs) {
  const files = sourceFiles(lib.dir).map(analyzeFile);
  const indexPath = path.join(lib.dir, 'src', 'index.ts');
  const indexA = files.find((f) => f.file === indexPath);
  // Names the barrel publishes (locally-listed + re-exported-from-submodule).
  const indexExports = new Set();
  const indexReExportFrom = new Map(); // name -> module specifier (for citation checks)
  if (indexA) {
    for (const n of indexA.names.keys()) indexExports.add(n);
    for (const [n, mod] of indexA.reExportsFrom) {
      indexExports.add(n);
      indexReExportFrom.set(n, mod);
    }
  }
  analyses.set(lib.slug, { lib, files, indexPath, indexExports, indexReExportFrom });
}

// A foundation lib = a lib that at least one OTHER lib lists as a dependency.
const foundationSlugs = new Set();
for (const lib of libs) {
  for (const dep of Object.keys(lib.dependencies)) {
    if (pkgToSlug.has(dep)) foundationSlugs.add(pkgToSlug.get(dep));
  }
}

// Whole-workspace importer index: for every (module-local) identifier, does any module in any lib
// reference it via an import binding whose source resolves to the declaring lib? We approximate
// cross-module use with: (1) the declaring lib's barrel re-exports it (public), or (2) some OTHER
// non-index module references the identifier AND imports it (by name) from a sibling module / the
// declaring lib's package. We use name-reference + import-presence as the pragmatic, real signal.
function isImportedAnywhere(name, ownerSlug) {
  for (const [slug, a] of analyses) {
    for (const f of a.files) {
      if (f.file === a.indexPath) continue; // the barrel is handled separately (public surface)
      // same-lib sibling module referencing the name (and importing it) → used
      if (slug === ownerSlug) {
        if (f.importedIdentifiers.has(name) && f.referenced.has(name)) return true;
      } else {
        // cross-lib: referenced AND imported from the owner's package
        if (f.importedIdentifiers.has(name) && f.referenced.has(name)) {
          for (const mod of f.importsByName.values()) {
            if (pkgToSlug.get(mod) === ownerSlug) return true;
          }
        }
      }
    }
  }
  return false;
}

const findings = [];

// (A) DEAD-EXPORT scan: a non-index exported symbol not on the barrel and not imported anywhere.
for (const [slug, a] of analyses) {
  for (const f of a.files) {
    if (f.file === a.indexPath) continue;
    for (const [name, info] of f.names) {
      if (a.indexExports.has(name)) continue; // re-exported by the barrel → public API, exempt
      if (isImportedAnywhere(name, slug)) continue; // consumed by some module → reachable
      findings.push({
        slug,
        kind: 'dead-export',
        file: f.file,
        line: info.line,
        name,
        message:
          `dead export '${name}' (${info.kind}) — declared in a non-index module, NOT on the ` +
          `public barrel (src/index.ts) and imported by NO module across the TS libs. Either ` +
          `re-export it from index.ts (make it public API) or DELETE it. (ADR-0024 one-concept-` +
          `one-home: every exported symbol has a producer or consumer.)`,
      });
    }
  }
}

// (B) CROSS-LIB MATH DUPLICATION: a downstream lib re-declares (not cites) a foundation export name.
// Build the foundation export catalog: name -> {slug, kind}.
const foundationExports = new Map(); // name -> { slug, kind }
for (const fslug of foundationSlugs) {
  const a = analyses.get(fslug);
  if (!a) continue;
  for (const f of a.files) {
    for (const [name, info] of f.names) {
      // only math-bearing exports: a const seed/table or a function (the generator surface)
      if (info.kind === 'function' || info.isMathConst) {
        if (!foundationExports.has(name)) foundationExports.set(name, { slug: fslug, kind: info.kind });
      }
    }
  }
}

// The barrel re-exporting the foundation symbol (`export { stepAt } from '@eden/scale'`) is a pure
// citation — never a re-derivation — so it is always exempt.
function barrelCites(a, name, ownerPkg) {
  return a.indexReExportFrom.get(name) === ownerPkg;
}
// A LOCAL re-declaration of a foundation symbol name in a given FILE is exempt only when THAT SAME
// FILE imports the foundation symbol (alias-blind) — the deliberate "keep the frozen-public value +
// assert it equals the cited foundation value at module load" pattern (theme/typography.ts keeps
// `DEFAULT_TYPE_RATIO = 1.2` AND imports scale's `DEFAULT_TYPE_RATIO as SCALE_TYPE_RATIO`, throwing if
// they drift). A re-declaration in a file that does NOT cite the foundation is a silent re-derivation
// — citing the symbol in a SIBLING module does not license re-spelling it here (one concept, one home).
function fileCitesFoundationSymbol(f, name, ownerPkg) {
  return f.importsByName.get(name) === ownerPkg || f.importsOriginalByModule.get(name) === ownerPkg;
}

for (const [slug, a] of analyses) {
  if (foundationSlugs.has(slug)) continue; // a foundation lib owns its own names
  for (const f of a.files) {
    for (const [name, info] of f.names) {
      if (!foundationExports.has(name)) continue;
      const owner = foundationExports.get(name);
      if (owner.slug === slug) continue;
      const ownerPkg = bySlug.get(owner.slug)?.pkgName;
      if (barrelCites(a, name, ownerPkg)) continue; // a cited barrel re-export — fine
      if (fileCitesFoundationSymbol(f, name, ownerPkg)) continue; // same-file cited + drift-guarded
      // A locally re-declared const/function colliding with the foundation's export = re-derivation.
      if (info.kind === 'function' || info.isMathConst) {
        findings.push({
          slug,
          kind: 'math-duplication',
          file: f.file,
          line: info.line,
          name,
          message:
            `cross-lib math duplication: '${name}' (${info.kind}) is already exported by the ` +
            `foundation lib '${owner.slug}' (${ownerPkg}). The generator/ratio math lives ONCE in ` +
            `the foundation — IMPORT and CITE it (\`import { ${name} } from '${ownerPkg}'\`), never ` +
            `re-derive it locally. (ADR-0024 cross-lib cohesion: theme cites scale, never re-implements.)`,
        });
      }
    }
  }
}

// ── report ──────────────────────────────────────────────────────────────────────────────────────
const scoped = onlyLib ? findings.filter((f) => f.slug === onlyLib) : findings;

if (scoped.length === 0) {
  const scopeNote = onlyLib ? ` (lib '${onlyLib}')` : ` (${libs.length} TS lib(s))`;
  process.stdout.write(`cohesion-scan: clean${scopeNote} — no dead exports, no cross-lib math duplication\n`);
  process.exit(0);
}

process.stderr.write(`cohesion-scan: ${scoped.length} violation(s)${onlyLib ? ` in '${onlyLib}'` : ''}:\n`);
for (const v of scoped) {
  const rel = path.relative(WORKSPACE, v.file);
  process.stderr.write(`  [${v.kind}] ${rel}:${v.line}\n    ${v.message}\n`);
}
process.exit(1);
