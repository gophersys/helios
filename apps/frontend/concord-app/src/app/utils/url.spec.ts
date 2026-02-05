import { isSafeUrl } from './url';

describe('isSafeUrl', () => {
  it('returns true for http://example.com', () => {
    expect(isSafeUrl('http://example.com')).toBe(true);
  });

  it('returns true for https://example.com', () => {
    expect(isSafeUrl('https://example.com')).toBe(true);
  });

  it('returns false for javascript:alert(1)', () => {
    expect(isSafeUrl('javascript:alert(1)')).toBe(false);
  });

  it('returns false for data:text/html,...', () => {
    expect(isSafeUrl('data:text/html,<h1>test</h1>')).toBe(false);
  });

  it('returns false for ftp://example.com', () => {
    expect(isSafeUrl('ftp://example.com')).toBe(false);
  });

  it('returns false for empty string', () => {
    expect(isSafeUrl('')).toBe(false);
  });

  it('returns false for invalid URL', () => {
    expect(isSafeUrl('not a url')).toBe(false);
  });
});
