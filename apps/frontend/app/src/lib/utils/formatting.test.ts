/**
 * Unit tests for formatting utilities.
 * Run with: npm test
 */
import { describe, it, expect } from 'vitest';
import {
  formatDate,
  formatDateTime,
  formatTimeAgo,
  formatSize,
  formatDuration,
  formatPercentage,
  formatNumber,
  formatCompactNumber,
  truncate,
  capitalize,
  titleCase,
  kebabCase,
  pluralize
} from './formatting';

describe('formatDate', () => {
  it('returns "Never" for null', () => {
    expect(formatDate(null)).toBe('Never');
  });

  it('formats a valid ISO date', () => {
    const result = formatDate('2024-01-15T10:30:00Z');
    expect(result).toMatch(/Jan/);
    expect(result).toMatch(/15/);
    expect(result).toMatch(/2024/);
  });
});

describe('formatTimeAgo', () => {
  it('returns "just now" for recent times', () => {
    const now = new Date().toISOString();
    expect(formatTimeAgo(now)).toBe('just now');
  });

  it('returns minutes for times under an hour', () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(formatTimeAgo(fiveMinutesAgo)).toBe('5m ago');
  });

  it('returns hours for times under a day', () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    expect(formatTimeAgo(twoHoursAgo)).toBe('2h ago');
  });

  it('returns days for times under a week', () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatTimeAgo(threeDaysAgo)).toBe('3d ago');
  });
});

describe('formatSize', () => {
  it('returns "-" for null', () => {
    expect(formatSize(null)).toBe('-');
  });

  it('formats bytes', () => {
    expect(formatSize('500')).toBe('500 B');
  });

  it('formats kilobytes', () => {
    expect(formatSize('2048')).toBe('2.0 KB');
  });

  it('formats megabytes', () => {
    expect(formatSize('5242880')).toBe('5.0 MB');
  });

  it('formats gigabytes', () => {
    expect(formatSize('1073741824')).toBe('1.00 GB');
  });
});

describe('formatDuration', () => {
  it('formats milliseconds', () => {
    expect(formatDuration(500)).toBe('500ms');
  });

  it('formats seconds', () => {
    expect(formatDuration(5000)).toBe('5s');
  });

  it('formats minutes and seconds', () => {
    expect(formatDuration(90000)).toBe('1m 30s');
  });

  it('formats hours and minutes', () => {
    expect(formatDuration(5400000)).toBe('1h 30m');
  });

  it('formats days', () => {
    expect(formatDuration(90000000)).toBe('1d 1h');
  });

  it('returns "-" for negative values', () => {
    expect(formatDuration(-100)).toBe('-');
  });
});

describe('formatPercentage', () => {
  it('formats a percentage', () => {
    expect(formatPercentage(75.5)).toBe('75.5%');
  });

  it('converts ratio to percentage', () => {
    expect(formatPercentage(0.755, 1, true)).toBe('75.5%');
  });

  it('respects decimal places', () => {
    expect(formatPercentage(33.3333, 2)).toBe('33.33%');
  });
});

describe('formatCompactNumber', () => {
  it('returns small numbers as-is', () => {
    expect(formatCompactNumber(500)).toBe('500');
  });

  it('formats thousands', () => {
    expect(formatCompactNumber(1500)).toBe('1.5K');
  });

  it('formats millions', () => {
    expect(formatCompactNumber(1500000)).toBe('1.5M');
  });

  it('formats billions', () => {
    expect(formatCompactNumber(1500000000)).toBe('1.5B');
  });
});

describe('truncate', () => {
  it('returns short strings unchanged', () => {
    expect(truncate('Hello', 10)).toBe('Hello');
  });

  it('truncates long strings', () => {
    expect(truncate('Hello World', 8)).toBe('Hello...');
  });

  it('uses custom suffix', () => {
    expect(truncate('Hello World', 9, '…')).toBe('Hello Wo…');
  });
});

describe('capitalize', () => {
  it('capitalizes first letter', () => {
    expect(capitalize('hello')).toBe('Hello');
  });

  it('handles empty string', () => {
    expect(capitalize('')).toBe('');
  });
});

describe('titleCase', () => {
  it('converts camelCase to Title Case', () => {
    expect(titleCase('myVariableName')).toBe('My Variable Name');
  });

  it('converts PascalCase to Title Case', () => {
    expect(titleCase('MyVariableName')).toBe('My Variable Name');
  });
});

describe('kebabCase', () => {
  it('converts camelCase to kebab-case', () => {
    expect(kebabCase('myVariableName')).toBe('my-variable-name');
  });

  it('converts spaces to dashes', () => {
    expect(kebabCase('my variable name')).toBe('my-variable-name');
  });
});

describe('pluralize', () => {
  it('returns singular for count of 1', () => {
    expect(pluralize(1, 'item')).toBe('1 item');
  });

  it('returns plural for count > 1', () => {
    expect(pluralize(5, 'item')).toBe('5 items');
  });

  it('uses custom plural', () => {
    expect(pluralize(5, 'child', 'children')).toBe('5 children');
  });

  it('returns plural for count of 0', () => {
    expect(pluralize(0, 'item')).toBe('0 items');
  });
});
