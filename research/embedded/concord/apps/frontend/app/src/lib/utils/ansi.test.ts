/**
 * Unit tests for ANSI escape code parser.
 */
import { describe, it, expect } from 'vitest';
import { parseAnsi, stripAnsi } from './ansi';

// ── parseAnsi ─────────────────────────────────────────────────────────────────

describe('parseAnsi', () => {
  describe('plain text (no codes)', () => {
    it('returns a single segment with empty classes for plain text', () => {
      const result = parseAnsi('hello world');
      expect(result).toEqual([{ text: 'hello world', classes: '' }]);
    });

    it('returns a single segment for empty string', () => {
      const result = parseAnsi('');
      expect(result).toEqual([{ text: '', classes: '' }]);
    });
  });

  describe('standard foreground colors', () => {
    it('maps red (31) to text-error', () => {
      const result = parseAnsi('\x1b[31mERROR\x1b[0m');
      expect(result[0]).toEqual({ text: 'ERROR', classes: 'text-error' });
    });

    it('maps green (32) to text-success', () => {
      const result = parseAnsi('\x1b[32mOK\x1b[0m');
      expect(result[0]).toEqual({ text: 'OK', classes: 'text-success' });
    });

    it('maps yellow (33) to text-warning', () => {
      const result = parseAnsi('\x1b[33mWARN\x1b[0m');
      expect(result[0]).toEqual({ text: 'WARN', classes: 'text-warning' });
    });

    it('maps blue (34) to text-accent', () => {
      const result = parseAnsi('\x1b[34mINFO\x1b[0m');
      expect(result[0]).toEqual({ text: 'INFO', classes: 'text-accent' });
    });

    it('maps magenta (35) to ansi-magenta', () => {
      const result = parseAnsi('\x1b[35mPURPLE\x1b[0m');
      expect(result[0]).toEqual({ text: 'PURPLE', classes: 'ansi-magenta' });
    });

    it('maps cyan (36) to text-info', () => {
      const result = parseAnsi('\x1b[36mCYAN\x1b[0m');
      expect(result[0]).toEqual({ text: 'CYAN', classes: 'text-info' });
    });

    it('maps white (37) to text-text-secondary', () => {
      const result = parseAnsi('\x1b[37mWHITE\x1b[0m');
      expect(result[0]).toEqual({ text: 'WHITE', classes: 'text-text-secondary' });
    });

    it('maps black (30) to ansi-black', () => {
      const result = parseAnsi('\x1b[30mBLACK\x1b[0m');
      expect(result[0]).toEqual({ text: 'BLACK', classes: 'ansi-black' });
    });
  });

  describe('bright foreground colors', () => {
    it('maps bright black (90) to text-text-tertiary', () => {
      const result = parseAnsi('\x1b[90mdimmed\x1b[0m');
      expect(result[0]).toEqual({ text: 'dimmed', classes: 'text-text-tertiary' });
    });

    it('maps bright red (91) to ansi-bright-red', () => {
      const result = parseAnsi('\x1b[91mbright red\x1b[0m');
      expect(result[0]).toEqual({ text: 'bright red', classes: 'ansi-bright-red' });
    });

    it('maps bright white (97) to text-text-primary', () => {
      const result = parseAnsi('\x1b[97mbright white\x1b[0m');
      expect(result[0]).toEqual({ text: 'bright white', classes: 'text-text-primary' });
    });

    it('maps bright green (92)', () => {
      const result = parseAnsi('\x1b[92mbright green\x1b[0m');
      expect(result[0]).toEqual({ text: 'bright green', classes: 'ansi-bright-green' });
    });

    it('maps bright yellow (93)', () => {
      const result = parseAnsi('\x1b[93mbright yellow\x1b[0m');
      expect(result[0]).toEqual({ text: 'bright yellow', classes: 'ansi-bright-yellow' });
    });

    it('maps bright blue (94)', () => {
      const result = parseAnsi('\x1b[94mbright blue\x1b[0m');
      expect(result[0]).toEqual({ text: 'bright blue', classes: 'ansi-bright-blue' });
    });

    it('maps bright magenta (95)', () => {
      const result = parseAnsi('\x1b[95mbright magenta\x1b[0m');
      expect(result[0]).toEqual({ text: 'bright magenta', classes: 'ansi-bright-magenta' });
    });

    it('maps bright cyan (96)', () => {
      const result = parseAnsi('\x1b[96mbright cyan\x1b[0m');
      expect(result[0]).toEqual({ text: 'bright cyan', classes: 'ansi-bright-cyan' });
    });
  });

  describe('style codes', () => {
    it('maps bold (1) to font-bold', () => {
      const result = parseAnsi('\x1b[1mBOLD\x1b[0m');
      expect(result[0]).toEqual({ text: 'BOLD', classes: 'font-bold' });
    });

    it('maps dim (2) to opacity-70', () => {
      const result = parseAnsi('\x1b[2mdim\x1b[0m');
      expect(result[0]).toEqual({ text: 'dim', classes: 'opacity-70' });
    });

    it('maps italic (3) to italic', () => {
      const result = parseAnsi('\x1b[3mitalic\x1b[0m');
      expect(result[0]).toEqual({ text: 'italic', classes: 'italic' });
    });
  });

  describe('unknown codes', () => {
    it('ignores unknown ANSI codes and produces no class', () => {
      // Code 42 (background green) is not mapped
      const result = parseAnsi('\x1b[42mtext\x1b[0m');
      expect(result[0]).toEqual({ text: 'text', classes: '' });
    });
  });

  describe('reset code (0)', () => {
    it('reset clears current classes', () => {
      const result = parseAnsi('\x1b[31mred\x1b[0m normal');
      expect(result[0]).toEqual({ text: 'red', classes: 'text-error' });
      expect(result[1]).toEqual({ text: ' normal', classes: '' });
    });

    it('empty code sequence acts as reset', () => {
      // \x1b[m with no code is treated as reset
      const result = parseAnsi('\x1b[31mred\x1b[mnormal');
      expect(result[0]).toEqual({ text: 'red', classes: 'text-error' });
      expect(result[1]).toEqual({ text: 'normal', classes: '' });
    });
  });

  describe('multi-code sequences', () => {
    it('combines bold and color in one sequence', () => {
      const result = parseAnsi('\x1b[1;31mBOLD RED\x1b[0m');
      expect(result[0].classes).toContain('font-bold');
      expect(result[0].classes).toContain('text-error');
      expect(result[0].text).toBe('BOLD RED');
    });

    it('accumulates classes across sequential escape codes', () => {
      const result = parseAnsi('\x1b[1m\x1b[32mBOLD GREEN\x1b[0m');
      expect(result[0].classes).toContain('font-bold');
      expect(result[0].classes).toContain('text-success');
    });

    it('handles multiple segments with different colors', () => {
      const result = parseAnsi('\x1b[31mfail\x1b[0m \x1b[32mpass\x1b[0m');
      expect(result[0]).toEqual({ text: 'fail', classes: 'text-error' });
      expect(result[1]).toEqual({ text: ' ', classes: '' });
      expect(result[2]).toEqual({ text: 'pass', classes: 'text-success' });
    });

    it('handles text before first escape code', () => {
      const result = parseAnsi('prefix \x1b[31merror\x1b[0m');
      expect(result[0]).toEqual({ text: 'prefix ', classes: '' });
      expect(result[1]).toEqual({ text: 'error', classes: 'text-error' });
    });

    it('handles text after last escape code with no trailing reset', () => {
      const result = parseAnsi('\x1b[32mgreen text');
      expect(result[0]).toEqual({ text: 'green text', classes: 'text-success' });
    });
  });

  describe('Unicode control picture normalization', () => {
    it('treats Unicode ESC picture (U+241B) same as real escape', () => {
      // ␛[31m — Unicode control picture for ESC
      const result = parseAnsi('\u241b[31mred\u241b[0m');
      expect(result[0]).toEqual({ text: 'red', classes: 'text-error' });
    });

    it('handles mixed real escapes and Unicode pictures', () => {
      const result = parseAnsi('\x1b[32mgreen\x1b[0m \u241b[31mred\u241b[0m');
      expect(result[0]).toEqual({ text: 'green', classes: 'text-success' });
      expect(result[2]).toEqual({ text: 'red', classes: 'text-error' });
    });
  });

  describe('memoization', () => {
    it('returns the same array reference for repeated calls', () => {
      const line = '\x1b[32mCached\x1b[0m';
      const first = parseAnsi(line);
      const second = parseAnsi(line);
      expect(first).toBe(second); // same reference, not just equal
    });

    it('returns different results for different inputs', () => {
      const a = parseAnsi('\x1b[31mred\x1b[0m');
      const b = parseAnsi('\x1b[32mgreen\x1b[0m');
      expect(a).not.toBe(b);
      expect(a[0].classes).toBe('text-error');
      expect(b[0].classes).toBe('text-success');
    });
  });

  describe('realistic log lines', () => {
    it('parses a typical build log success line', () => {
      const line = '\x1b[32m[  0.000]\x1b[0m Build started';
      const result = parseAnsi(line);
      expect(result[0]).toEqual({ text: '[  0.000]', classes: 'text-success' });
      expect(result[1]).toEqual({ text: ' Build started', classes: '' });
    });

    it('parses a pytest PASSED line', () => {
      const line = '\x1b[32mPASSED\x1b[0m tests/test_foo.py::test_bar';
      const result = parseAnsi(line);
      expect(result[0].classes).toBe('text-success');
      expect(result[0].text).toBe('PASSED');
    });

    it('parses a pytest FAILED line', () => {
      const line = '\x1b[31mFAILED\x1b[0m tests/test_foo.py::test_bar';
      const result = parseAnsi(line);
      expect(result[0].classes).toBe('text-error');
      expect(result[0].text).toBe('FAILED');
    });
  });
});

// ── stripAnsi ─────────────────────────────────────────────────────────────────

describe('stripAnsi', () => {
  it('removes real escape sequences', () => {
    expect(stripAnsi('\x1b[31mred\x1b[0m')).toBe('red');
  });

  it('removes Unicode control picture sequences', () => {
    expect(stripAnsi('\u241b[32mgreen\u241b[0m')).toBe('green');
  });

  it('removes multiple codes from a line', () => {
    expect(stripAnsi('\x1b[1m\x1b[32mBOLD GREEN\x1b[0m')).toBe('BOLD GREEN');
  });

  it('passes through plain text unchanged', () => {
    expect(stripAnsi('no codes here')).toBe('no codes here');
  });

  it('handles empty string', () => {
    expect(stripAnsi('')).toBe('');
  });

  it('removes multi-code sequences', () => {
    expect(stripAnsi('\x1b[1;31mbold red\x1b[0m')).toBe('bold red');
  });

  it('strips from a realistic log line', () => {
    const raw = '\x1b[32m[PASS]\x1b[0m test_foo: \x1b[31m0 errors\x1b[0m';
    expect(stripAnsi(raw)).toBe('[PASS] test_foo: 0 errors');
  });
});
