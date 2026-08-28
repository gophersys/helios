import { describe, it, expect } from 'vitest';
import { ACTIONABLE_IDS, isActionableId } from './registry';

describe('actionable registry', () => {
  it('has no duplicate IDs', () => {
    const unique = new Set(ACTIONABLE_IDS);
    expect(unique.size).toBe(ACTIONABLE_IDS.length);
  });

  it('all IDs are kebab-case lowercase', () => {
    for (const id of ACTIONABLE_IDS) {
      expect(id).toMatch(/^[a-z][a-z0-9-]*$/);
    }
  });

  it('isActionableId returns true for registered IDs', () => {
    expect(isActionableId('upload-fw')).toBe(true);
    expect(isActionableId('new-product')).toBe(true);
  });

  it('isActionableId returns false for unknown IDs', () => {
    expect(isActionableId('nonexistent')).toBe(false);
    expect(isActionableId('')).toBe(false);
    expect(isActionableId('UPLOAD-FW')).toBe(false); // case-sensitive
  });
});
