export function formatDate(iso: string | null): string {
  if (!iso) return 'Never';
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/**
 * Format a UTC timestamp as Phoenix-local date + time. Multiple releases
 * land per day now, so the date alone isn't enough to disambiguate them
 * in any list view; pinning to Phoenix (America/Phoenix, no DST) keeps
 * the displayed time consistent regardless of which timezone the
 * operator's browser thinks it's in.
 *
 * Output: ``Apr 27 · 2:25 PM PHX``.
 */
export function formatPhoenixTime(iso: string | null): string {
  if (!iso) return 'Never';
  const date = new Date(iso);
  const datePart = date.toLocaleDateString('en-US', {
    timeZone: 'America/Phoenix',
    month: 'short',
    day: 'numeric',
  });
  const timePart = date.toLocaleTimeString('en-US', {
    timeZone: 'America/Phoenix',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
  return `${datePart} · ${timePart} PHX`;
}

export function formatTimeAgo(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return diffMins + 'm ago';
  if (diffHours < 24) return diffHours + 'h ago';
  if (diffDays < 7) return diffDays + 'd ago';

  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

export function formatSize(bytes: string | null): string {
  if (!bytes) return '-';
  const n = parseInt(bytes, 10);
  if (isNaN(n)) return '-';
  if (n < 1024) return n + ' B';
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
  if (n < 1024 * 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + ' MB';
  return (n / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

/**
 * Format a duration in milliseconds to a human-readable string.
 * @example formatDuration(90000) // "1m 30s"
 */
export function formatDuration(ms: number): string {
  if (ms < 0) return '-';
  if (ms < 1000) return Math.round(ms) + 'ms';

  const seconds = Math.floor(ms / 1000) % 60;
  const minutes = Math.floor(ms / 60000) % 60;
  const hours = Math.floor(ms / 3600000) % 24;
  const days = Math.floor(ms / 86400000);

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (seconds > 0 && days === 0) parts.push(`${seconds}s`);

  return parts.join(' ') || '0s';
}

/**
 * Format a percentage value.
 * @example formatPercentage(75.5) // "75.5%"
 * @example formatPercentage(0.755, 1, true) // "75.5%" (from ratio)
 */
export function formatPercentage(value: number, decimals = 1, isRatio = false): string {
  const pct = isRatio ? value * 100 : value;
  return pct.toFixed(decimals) + '%';
}

/**
 * Format a number with thousand separators.
 * @example formatNumber(1234567) // "1,234,567"
 */
export function formatNumber(n: number, locale?: string): string {
  return n.toLocaleString(locale);
}

/**
 * Format a number with compact notation (K, M, B).
 * @example formatCompactNumber(1234567) // "1.2M"
 */
export function formatCompactNumber(n: number, decimals = 1): string {
  if (n < 1000) return String(n);
  if (n < 1000000) return (n / 1000).toFixed(decimals) + 'K';
  if (n < 1000000000) return (n / 1000000).toFixed(decimals) + 'M';
  return (n / 1000000000).toFixed(decimals) + 'B';
}

/**
 * Truncate a string to a maximum length with ellipsis.
 * @example truncate("Hello World", 8) // "Hello..."
 */
export function truncate(str: string, maxLength: number, suffix = '...'): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - suffix.length) + suffix;
}

/**
 * Capitalize the first letter of a string.
 * @example capitalize("hello") // "Hello"
 */
export function capitalize(str: string): string {
  if (!str) return str;
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Convert camelCase or PascalCase to Title Case.
 * @example titleCase("myVariableName") // "My Variable Name"
 */
export function titleCase(str: string): string {
  return str
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase())
    .trim();
}

/**
 * Convert a string to kebab-case.
 * @example kebabCase("myVariableName") // "my-variable-name"
 */
export function kebabCase(str: string): string {
  return str
    .replace(/([a-z])([A-Z])/g, '$1-$2')
    .replace(/[\s_]+/g, '-')
    .toLowerCase();
}

/**
 * Pluralize a word based on count.
 * @example pluralize(1, "item") // "1 item"
 * @example pluralize(5, "item") // "5 items"
 */
export function pluralize(count: number, singular: string, plural?: string): string {
  const word = count === 1 ? singular : (plural || singular + 's');
  return `${count} ${word}`;
}

// ANSI color code mapping to CSS classes
const ANSI_COLORS: Record<number, string> = {
  // Standard colors (foreground 30-37)
  30: 'ansi-black',
  31: 'ansi-red',
  32: 'ansi-green',
  33: 'ansi-yellow',
  34: 'ansi-blue',
  35: 'ansi-magenta',
  36: 'ansi-cyan',
  37: 'ansi-white',
  // Bright colors (foreground 90-97)
  90: 'ansi-bright-black',
  91: 'ansi-bright-red',
  92: 'ansi-bright-green',
  93: 'ansi-bright-yellow',
  94: 'ansi-bright-blue',
  95: 'ansi-bright-magenta',
  96: 'ansi-bright-cyan',
  97: 'ansi-bright-white',
};

const ANSI_STYLES: Record<number, string> = {
  1: 'ansi-bold',
  2: 'ansi-dim',
  3: 'ansi-italic',
  4: 'ansi-underline',
};

/**
 * Convert ANSI escape sequences to HTML with CSS classes.
 * Handles common color codes and text styles.
 * @example ansiToHtml("\x1b[32mSuccess\x1b[0m") // '<span class="ansi-green">Success</span>'
 */
export function ansiToHtml(text: string): string {
  // Match ANSI escape sequences: ESC[...m
  const ansiRegex = /\x1b\[([0-9;]*)m/g;

  let result = '';
  let lastIndex = 0;
  let openSpans = 0;
  let match;

  while ((match = ansiRegex.exec(text)) !== null) {
    // Add text before this escape sequence (escaped for HTML)
    result += escapeHtml(text.slice(lastIndex, match.index));
    lastIndex = match.index + match[0].length;

    const codes = match[1].split(';').map(c => parseInt(c, 10) || 0);

    for (const code of codes) {
      if (code === 0) {
        // Reset - close all open spans
        while (openSpans > 0) {
          result += '</span>';
          openSpans--;
        }
      } else {
        const colorClass = ANSI_COLORS[code];
        const styleClass = ANSI_STYLES[code];
        const cssClass = colorClass || styleClass;

        if (cssClass) {
          result += `<span class="${cssClass}">`;
          openSpans++;
        }
      }
    }
  }

  // Add remaining text
  result += escapeHtml(text.slice(lastIndex));

  // Close any remaining open spans
  while (openSpans > 0) {
    result += '</span>';
    openSpans--;
  }

  return result;
}

/**
 * Escape HTML special characters.
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Strip ANSI escape sequences from text.
 * @example stripAnsi("\x1b[32mSuccess\x1b[0m") // "Success"
 */
export function stripAnsi(text: string): string {
  return text.replace(/\x1b\[[0-9;]*m/g, '');
}

/** Build log analysis result */
export interface LogAnalysis {
  errors: string[];
  warnings: string[];
  errorCount: number;
  warningCount: number;
}

/**
 * Check if a line starts a new warning or error block.
 */
function isNewErrorLine(line: string): boolean {
  return (
    /:\d+:\d+: error:/.test(line) ||
    /^error:/i.test(line) ||
    /undefined reference to/.test(line) ||
    /multiple definition of/.test(line) ||
    /^CMake Error/i.test(line) ||
    /^-- Configuring incomplete/i.test(line) ||
    /FAILED:|ninja: build stopped/i.test(line) ||
    /error: Aborting due to Kconfig/.test(line)
  );
}

function isNewWarningLine(line: string): boolean {
  return (
    /:\d+:\d+: warning:/.test(line) ||
    /^warning:/i.test(line) ||
    /^CMake Warning/i.test(line) ||
    (/deprecated/i.test(line) && /warning/i.test(line))
  );
}

/**
 * Analyze build log for errors and warnings.
 * Extracts GCC/compiler errors, linker errors, and build system warnings.
 * Captures multi-line messages (Kconfig warnings, CMake warnings, etc.)
 */
export function analyzeBuildLog(log: string): LogAnalysis {
  const errors: string[] = [];
  const warnings: string[] = [];

  const lines = log.split('\n');

  let currentEntry: string[] = [];
  let currentType: 'error' | 'warning' | null = null;

  function flushEntry() {
    if (currentEntry.length > 0 && currentType) {
      const message = currentEntry.join(' ').trim();
      if (currentType === 'error') {
        errors.push(message);
      } else {
        warnings.push(message);
      }
    }
    currentEntry = [];
    currentType = null;
  }

  for (let i = 0; i < lines.length; i++) {
    const stripped = stripAnsi(lines[i]);
    const trimmed = stripped.trim();

    // Skip empty lines - they end multi-line entries
    if (!trimmed) {
      flushEntry();
      continue;
    }

    // Check if this starts a new error
    if (isNewErrorLine(stripped)) {
      flushEntry();
      currentType = 'error';
      currentEntry.push(trimmed);
      continue;
    }

    // Check if this starts a new warning
    if (isNewWarningLine(stripped)) {
      flushEntry();
      currentType = 'warning';
      currentEntry.push(trimmed);
      continue;
    }

    // If we're currently collecting an entry, append continuation lines
    // Continuation lines typically start with whitespace or are indented
    if (currentType && currentEntry.length > 0) {
      // If line starts with whitespace or looks like a continuation (not a new log line)
      if (/^\s/.test(stripped) || !/^[[\-\d]/.test(stripped)) {
        currentEntry.push(trimmed);
      } else {
        // This looks like a new unrelated line, flush and skip
        flushEntry();
      }
    }
  }

  // Flush any remaining entry
  flushEntry();

  return {
    errors,
    warnings,
    errorCount: errors.length,
    warningCount: warnings.length,
  };
}
