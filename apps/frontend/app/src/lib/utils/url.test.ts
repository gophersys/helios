/**
 * Tests for URL validation utilities.
 * Critical for XSS prevention.
 */
import { describe, it, expect } from 'vitest';
import { isSafeUrl } from './url';

describe('isSafeUrl', () => {
  describe('Valid URLs', () => {
    it('allows https URLs', () => {
      expect(isSafeUrl('https://example.com')).toBe(true);
      expect(isSafeUrl('https://example.com/path')).toBe(true);
      expect(isSafeUrl('https://example.com/path?query=1')).toBe(true);
      expect(isSafeUrl('https://sub.example.com')).toBe(true);
    });

    it('allows http URLs', () => {
      expect(isSafeUrl('http://example.com')).toBe(true);
      expect(isSafeUrl('http://localhost:3000')).toBe(true);
      expect(isSafeUrl('http://192.168.1.1')).toBe(true);
    });

    it('allows URLs with ports', () => {
      expect(isSafeUrl('https://example.com:8080')).toBe(true);
      expect(isSafeUrl('http://localhost:4200')).toBe(true);
    });

    it('allows URLs with authentication', () => {
      expect(isSafeUrl('https://user:pass@example.com')).toBe(true);
    });

    it('allows URLs with fragments', () => {
      expect(isSafeUrl('https://example.com#section')).toBe(true);
    });
  });

  describe('Invalid/Dangerous URLs', () => {
    it('rejects null', () => {
      expect(isSafeUrl(null)).toBe(false);
    });

    it('rejects undefined', () => {
      expect(isSafeUrl(undefined)).toBe(false);
    });

    it('rejects empty string', () => {
      expect(isSafeUrl('')).toBe(false);
    });

    it('rejects javascript: protocol (XSS)', () => {
      expect(isSafeUrl('javascript:alert(1)')).toBe(false);
      expect(isSafeUrl('javascript:void(0)')).toBe(false);
      expect(isSafeUrl('JAVASCRIPT:alert(1)')).toBe(false);
    });

    it('rejects data: protocol', () => {
      expect(isSafeUrl('data:text/html,<script>alert(1)</script>')).toBe(false);
      expect(isSafeUrl('data:image/png;base64,abc')).toBe(false);
    });

    it('rejects vbscript: protocol', () => {
      expect(isSafeUrl('vbscript:msgbox("XSS")')).toBe(false);
    });

    it('rejects file: protocol', () => {
      expect(isSafeUrl('file:///etc/passwd')).toBe(false);
    });

    it('rejects ftp: protocol', () => {
      expect(isSafeUrl('ftp://ftp.example.com')).toBe(false);
    });

    it('rejects blob: protocol', () => {
      expect(isSafeUrl('blob:https://example.com/uuid')).toBe(false);
    });

    it('rejects malformed URLs', () => {
      expect(isSafeUrl('not-a-url')).toBe(false);
      expect(isSafeUrl('example.com')).toBe(false);
      expect(isSafeUrl('/relative/path')).toBe(false);
      expect(isSafeUrl('://missing-protocol.com')).toBe(false);
    });

    it('rejects URLs with whitespace tricks', () => {
      expect(isSafeUrl('  javascript:alert(1)')).toBe(false);
      expect(isSafeUrl('\njavascript:alert(1)')).toBe(false);
    });
  });
});
