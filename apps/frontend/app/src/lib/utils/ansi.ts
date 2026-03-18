/**
 * ANSI escape code parser — converts ANSI sequences to styled segments.
 *
 * Used by build logs and UART terminals to render colored output.
 * Supports standard + bright foreground colors and bold/dim/italic styles.
 */

export interface AnsiSegment {
  text: string;
  classes: string;
}

function ansiToClass(code: string): string {
  switch (code) {
    // Standard foreground colors
    case '30': return 'ansi-black';
    case '31': return 'text-error';         // red
    case '32': return 'text-success';       // green
    case '33': return 'text-warning';       // yellow
    case '34': return 'text-accent';        // blue
    case '35': return 'ansi-magenta';
    case '36': return 'text-info';          // cyan
    case '37': return 'text-text-secondary';
    // Bright foreground colors
    case '90': return 'text-text-tertiary';
    case '91': return 'ansi-bright-red';
    case '92': return 'ansi-bright-green';
    case '93': return 'ansi-bright-yellow';
    case '94': return 'ansi-bright-blue';
    case '95': return 'ansi-bright-magenta';
    case '96': return 'ansi-bright-cyan';
    case '97': return 'text-text-primary';
    // Styles
    case '1': return 'font-bold';
    case '2': return 'opacity-70';
    case '3': return 'italic';
    default: return '';
  }
}

// --- Memoization cache for parseAnsi ---
// Lines are immutable strings that never change after creation, so parsed
// results can be cached indefinitely.  We cap size to avoid memory leaks
// on very long-running sessions.
const _parseCache = new Map<string, AnsiSegment[]>();
const _PARSE_CACHE_MAX = 5000;

/**
 * Parse a line containing ANSI escape codes into styled segments.
 *
 * Results are memoized per input string — repeated calls with the same
 * line return the cached result instantly.
 *
 * Handles both real escape codes (\x1b[...m) and Unicode control pictures (␛[...m).
 */
export function parseAnsi(line: string): AnsiSegment[] {
  const cached = _parseCache.get(line);
  if (cached) return cached;

  // Normalize Unicode control picture (␛) to real escape
  const normalized = line.replace(/\u241b/g, '\x1b');

  const segments: AnsiSegment[] = [];
  const regex = /\x1b\[([0-9;]*)m/g;
  let lastIndex = 0;
  let currentClasses = '';
  let match: RegExpExecArray | null;

  while ((match = regex.exec(normalized)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ text: normalized.slice(lastIndex, match.index), classes: currentClasses });
    }
    const codes = match[1].split(';');
    for (const code of codes) {
      if (code === '0' || code === '') {
        currentClasses = '';
      } else {
        const cls = ansiToClass(code);
        if (cls) currentClasses = currentClasses ? `${currentClasses} ${cls}` : cls;
      }
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < normalized.length) {
    segments.push({ text: normalized.slice(lastIndex), classes: currentClasses });
  }

  if (segments.length === 0) {
    segments.push({ text: line, classes: '' });
  }

  // Evict oldest entries when cache is full
  if (_parseCache.size >= _PARSE_CACHE_MAX) {
    const first = _parseCache.keys().next().value;
    if (first !== undefined) _parseCache.delete(first);
  }
  _parseCache.set(line, segments);

  return segments;
}

/**
 * Strip all ANSI escape codes from a string (for search/filtering).
 */
export function stripAnsi(text: string): string {
  return text.replace(/\u241b\[[0-9;]*m/g, '').replace(/\x1b\[[0-9;]*m/g, '');
}
