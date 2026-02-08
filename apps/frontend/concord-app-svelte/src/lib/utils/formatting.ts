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
  if (ms < 1000) return ms + 'ms';

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
