import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { buildDeepLink, readActionFromUrl, highlightAction, DEEP_LINK_PARAM } from './deep-link';

describe('buildDeepLink', () => {
  it('adds the action param to a clean URL', () => {
    const url = new URL('https://concord.local/products/alpha');
    expect(buildDeepLink('upload-fw', url)).toBe(
      'https://concord.local/products/alpha?a=upload-fw',
    );
  });

  it('preserves existing query params (tab, revision, etc.)', () => {
    const url = new URL('https://concord.local/products/alpha?tab=assets&rev=b0');
    const result = new URL(buildDeepLink('upload-fw', url));
    expect(result.searchParams.get('tab')).toBe('assets');
    expect(result.searchParams.get('rev')).toBe('b0');
    expect(result.searchParams.get(DEEP_LINK_PARAM)).toBe('upload-fw');
  });

  it('replaces an existing action param', () => {
    const url = new URL('https://concord.local/products/alpha?a=old-action');
    const result = new URL(buildDeepLink('upload-fw', url));
    expect(result.searchParams.get(DEEP_LINK_PARAM)).toBe('upload-fw');
    expect(result.searchParams.getAll(DEEP_LINK_PARAM)).toHaveLength(1);
  });

  it('does not mutate the input URL', () => {
    const url = new URL('https://concord.local/products/alpha');
    buildDeepLink('upload-fw', url);
    expect(url.searchParams.has(DEEP_LINK_PARAM)).toBe(false);
  });
});

describe('readActionFromUrl', () => {
  it('returns the action id when present and valid', () => {
    const url = new URL('https://concord.local/products/alpha?a=upload-fw');
    expect(readActionFromUrl(url)).toBe('upload-fw');
  });

  it('returns null when the param is missing', () => {
    expect(readActionFromUrl(new URL('https://concord.local/products/alpha'))).toBe(null);
  });

  it('returns null when the param is not a known action', () => {
    const url = new URL('https://concord.local/products/alpha?a=notreal');
    expect(readActionFromUrl(url)).toBe(null);
  });
});

describe('highlightAction', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('finds the element, scrolls it in, adds the highlight class, removes after timeout', () => {
    const el = document.createElement('button');
    el.setAttribute('data-action', 'upload-fw');
    el.scrollIntoView = vi.fn();
    document.body.appendChild(el);

    expect(highlightAction('upload-fw')).toBe(true);
    expect(el.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' });
    expect(el.classList.contains('deep-link-highlight')).toBe(true);

    vi.advanceTimersByTime(2400);
    expect(el.classList.contains('deep-link-highlight')).toBe(false);
  });

  it('returns false when no matching element exists', () => {
    expect(highlightAction('upload-fw')).toBe(false);
  });
});
