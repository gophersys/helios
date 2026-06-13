// The markdown → token-tree seam for the Notion-grade block renderer (doc 12 §5,
// REQ-0028). Rather than parse to opaque HTML and reverse-engineer it with regex
// (the static render-html.mjs approach, which is fragile), the body renderer lexes
// markdown into marked's *token tree* and renders each block token as a real
// Svelte component. This module owns that lexing plus the two derivations the
// renderer and the outline share: stable heading slugs (the §-anchor ids) and
// GitHub-style admonition detection on blockquotes.
//
// The corpus is first-party (Eden's own documents and the worked example, doc 11),
// so the rendered output is trusted; if this surface ever renders third-party
// document text, sanitization belongs at the {@html} seams in the block
// components, not here.

import { Lexer, type Token, type Tokens } from 'marked';

export type { Token, Tokens };

// Lex a markdown string into marked's block-level token tree. gfm enables tables,
// strikethrough, and task lists; breaks stays off so paragraphs read as prose
// (matching MarkdownSection's prior configuration). Returns a flat ordered list of
// block tokens; inline structure lives inside each block's `tokens` array.
export function lexMarkdown(markdown: string): Token[] {
  return Lexer.lex(markdown ?? '', { gfm: true, breaks: false });
}

// ── heading slugs ────────────────────────────────────────────────────────────
// Stable, collision-free heading ids so every heading carries a §-anchor and the
// outline can deep-link to it. The slugger is stateful (it disambiguates repeated
// headings with a numeric suffix), so a fresh one is created per section render.

export class HeadingSlugger {
  private readonly seen = new Map<string, number>();

  slug(text: string): string {
    const base =
      text
        .toLowerCase()
        .trim()
        .replace(/<[^>]+>/g, '')
        .replace(/[^\w\s-]/g, '')
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-')
        .replace(/^-+|-+$/g, '') || 'section';
    const count = this.seen.get(base) ?? 0;
    this.seen.set(base, count + 1);
    return count === 0 ? base : `${base}-${count}`;
  }
}

// Plain text of a heading token (markdown stripped), for the slug + the outline
// label. marked keeps the heading's source in `text`; this removes the inline
// markdown syntax (emphasis/code/link) to a readable label.
export function headingPlainText(token: Tokens.Heading): string {
  return token.text
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/_([^_]+)_/g, '$1')
    .replace(/~~([^~]+)~~/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .trim();
}

// ── admonitions / callouts ─────────────────────────────────────────────────────
// GitHub-style admonitions: a blockquote whose first line is `[!NOTE]`,
// `[!WARNING]`, etc. (doc 12 §5: "render `> [!NOTE]`-style admonitions into
// Notion-style callout cards"). The kinds map onto the Eden token palette in
// Callout.svelte (Sage/Moss accents). A plain blockquote (no marker) is a 'quote'.

export type CalloutKind = 'note' | 'tip' | 'important' | 'warning' | 'caution' | 'quote';

const ADMONITION_KINDS: ReadonlySet<string> = new Set([
  'note',
  'tip',
  'important',
  'warning',
  'caution',
]);

// The marker and the whitespace/newline that follows it (GitHub puts the marker on
// its own line, so the trailing \s* consumes the line break before the body).
const ADMONITION_MARKER = /^\[!(\w+)\]\s*/i;

export interface CalloutInfo {
  readonly kind: CalloutKind;
  // A display title for the callout header ('Note', 'Warning', …); null for a
  // plain blockquote, which renders without a labeled header.
  readonly title: string | null;
}

// Inspect a blockquote token's leading paragraph for an admonition marker. When
// found, returns the kind + title and the marker is stripped from the paragraph
// token in place so the body renders without the `[!NOTE]` literal. A markerless
// blockquote returns the 'quote' kind unchanged.
export function readCallout(token: Tokens.Blockquote): CalloutInfo {
  const paragraph = firstParagraph(token.tokens);
  if (paragraph) {
    const match = ADMONITION_MARKER.exec(paragraph.text);
    if (match) {
      const word = match[1].toLowerCase();
      if (ADMONITION_KINDS.has(word)) {
        stripMarker(paragraph);
        const title = word.charAt(0).toUpperCase() + word.slice(1);
        return { kind: word as CalloutKind, title };
      }
    }
  }
  return { kind: 'quote', title: null };
}

// The blockquote's leading paragraph token, where an admonition marker would
// appear. Returns null when the blockquote opens with a non-paragraph block.
function firstParagraph(tokens: Token[]): Tokens.Paragraph | null {
  const firstBlock = tokens[0];
  if (!firstBlock || firstBlock.type !== 'paragraph') return null;
  return firstBlock as Tokens.Paragraph;
}

// Remove the `[!KIND]` marker from the paragraph token. Paragraph.svelte renders
// from `.text`, so that field is authoritative; `.raw` and the first inline text
// token are kept consistent for any other reader of the tree.
function stripMarker(paragraph: Tokens.Paragraph): void {
  const mutable = paragraph as { raw: string; text: string; tokens?: Token[] };
  mutable.text = mutable.text.replace(ADMONITION_MARKER, '');
  mutable.raw = mutable.raw.replace(ADMONITION_MARKER, '');
  const firstInline = mutable.tokens?.[0];
  if (firstInline && firstInline.type === 'text') {
    const inline = firstInline as { raw: string; text: string };
    inline.raw = inline.raw.replace(ADMONITION_MARKER, '');
    inline.text = inline.text.replace(ADMONITION_MARKER, '');
  }
}
