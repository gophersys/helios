// Synchronous, offline syntax highlighting for fenced code blocks (doc 12 §5,
// REQ-0028: "fenced code with syntax highlighting"). highlight.js is chosen over
// Shiki/starry-night because it runs fully synchronously in both the SvelteKit
// SSR pass and the browser — no WASM, no async initialization — and because it
// emits *semantic* class names (.hljs-keyword, .hljs-string, …) rather than inline
// colors, so the highlight palette is styled from the locked Eden tokens in
// CodeBlock.svelte instead of an imported third-party theme. The core build
// (`highlight.js/lib/core`) ships none of the ~190 bundled grammars; only the
// curated languages registered below are pulled into the bundle.

import hljs from 'highlight.js/lib/core';
import type { LanguageFn } from 'highlight.js';

import bash from 'highlight.js/lib/languages/bash';
import css from 'highlight.js/lib/languages/css';
import diff from 'highlight.js/lib/languages/diff';
import go from 'highlight.js/lib/languages/go';
import json from 'highlight.js/lib/languages/json';
import markdown from 'highlight.js/lib/languages/markdown';
import protobuf from 'highlight.js/lib/languages/protobuf';
import python from 'highlight.js/lib/languages/python';
import rust from 'highlight.js/lib/languages/rust';
import shell from 'highlight.js/lib/languages/shell';
import sql from 'highlight.js/lib/languages/sql';
import typescript from 'highlight.js/lib/languages/typescript';
import xml from 'highlight.js/lib/languages/xml';
import yaml from 'highlight.js/lib/languages/yaml';

// The curated language set — the languages Eden's corpus actually uses (Go is the
// backend floor per ADR-0003; the UI is TypeScript/Svelte; protobuf is the Connect
// contract language; yaml/json are the document/registry formats). Each entry maps
// the canonical name and its common aliases to the registered grammar. xml backs
// HTML/Svelte-template highlighting; typescript backs js/ts/svelte script bodies.
const LANGUAGE_REGISTRY: ReadonlyArray<readonly [string, LanguageFn]> = [
  ['bash', bash],
  ['css', css],
  ['diff', diff],
  ['go', go],
  ['json', json],
  ['markdown', markdown],
  ['protobuf', protobuf],
  ['python', python],
  ['rust', rust],
  ['shell', shell],
  ['sql', sql],
  ['typescript', typescript],
  ['xml', xml],
  ['yaml', yaml],
];

for (const [name, grammar] of LANGUAGE_REGISTRY) {
  hljs.registerLanguage(name, grammar);
}

// Aliases the fence info-string may use, mapped to a registered language. A fence
// language not in this map (and not a registered name) falls through to a plain,
// HTML-escaped render — never a thrown error.
const LANGUAGE_ALIASES: Readonly<Record<string, string>> = {
  ts: 'typescript',
  tsx: 'typescript',
  js: 'typescript',
  jsx: 'typescript',
  javascript: 'typescript',
  svelte: 'xml',
  html: 'xml',
  golang: 'go',
  proto: 'protobuf',
  py: 'python',
  rs: 'rust',
  sh: 'bash',
  zsh: 'bash',
  yml: 'yaml',
  md: 'markdown',
};

// A friendly display label for the fence language, shown on the code block's
// header (the chrome that also hosts the copy button).
const LANGUAGE_LABELS: Readonly<Record<string, string>> = {
  typescript: 'TypeScript',
  go: 'Go',
  protobuf: 'Protobuf',
  python: 'Python',
  rust: 'Rust',
  bash: 'Bash',
  shell: 'Shell',
  json: 'JSON',
  yaml: 'YAML',
  sql: 'SQL',
  css: 'CSS',
  xml: 'HTML',
  markdown: 'Markdown',
  diff: 'Diff',
};

export interface HighlightedCode {
  // The highlighted inner HTML for a <code> element (hljs spans), or HTML-escaped
  // plain text when the language is unknown. Safe to inject — hljs escapes the
  // source it wraps, and the escape() fallback escapes everything.
  readonly html: string;
  // The resolved canonical language ('typescript', 'go', …) or null when unknown.
  readonly language: string | null;
  // The human label for the block header ('TypeScript', 'Go', …); the raw info
  // string when unknown but non-empty; null when no language was given.
  readonly label: string | null;
}

// Resolve a fence info string ('ts', 'go', 'mermaid', '') to a registered language
// name, or null when none applies.
function resolveLanguage(info: string): string | null {
  const normalized = info.trim().toLowerCase();
  if (normalized === '') return null;
  const aliased = LANGUAGE_ALIASES[normalized] ?? normalized;
  return hljs.getLanguage(aliased) ? aliased : null;
}

// Escape text for safe HTML injection when no grammar applies (the plain-fence
// path). hljs.highlight already escapes the source it tokenizes.
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Highlight a code string under a fence language. Unknown languages render as
// escaped plain text so an unexpected fence never breaks the page (and never
// throws). Highlighting is wrapped so a grammar edge case degrades to plain text
// rather than failing the whole document render.
export function highlightCode(code: string, info: string): HighlightedCode {
  const language = resolveLanguage(info);
  const rawLabel = info.trim();
  if (language === null) {
    return {
      html: escapeHtml(code),
      language: null,
      label: rawLabel === '' ? null : rawLabel,
    };
  }
  const label = LANGUAGE_LABELS[language] ?? rawLabel;
  try {
    const { value } = hljs.highlight(code, { language, ignoreIllegals: true });
    return { html: value, language, label };
  } catch {
    return { html: escapeHtml(code), language, label };
  }
}
