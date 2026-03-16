/**
 * Unit tests for collection utilities.
 */
import { describe, it, expect } from 'vitest';
import {
  groupBy,
  groupByWithMeta,
  indexBy,
  uniqueBy,
  sortBy,
  partition,
  chunk,
  sum,
  minBy,
  maxBy,
  countBy
} from './collections';

describe('groupBy', () => {
  it('groups items by key', () => {
    const items = [
      { id: 1, category: 'A' },
      { id: 2, category: 'B' },
      { id: 3, category: 'A' }
    ];
    const result = groupBy(items, i => i.category);
    expect(result).toEqual({
      A: [{ id: 1, category: 'A' }, { id: 3, category: 'A' }],
      B: [{ id: 2, category: 'B' }]
    });
  });

  it('handles empty array', () => {
    expect(groupBy([], () => 'key')).toEqual({});
  });
});

describe('groupByWithMeta', () => {
  it('groups with metadata', () => {
    const items = [
      { id: 1, category: 'A', value: 10 },
      { id: 2, category: 'A', value: 20 }
    ];
    const result = groupByWithMeta(
      items,
      i => i.category,
      items => ({ count: items.length, total: items.reduce((s, i) => s + i.value, 0) })
    );
    expect(result.A.meta).toEqual({ count: 2, total: 30 });
  });
});

describe('indexBy', () => {
  it('creates lookup map', () => {
    const users = [
      { id: 'a', name: 'Alice' },
      { id: 'b', name: 'Bob' }
    ];
    const result = indexBy(users, u => u.id);
    expect(result.a.name).toBe('Alice');
    expect(result.b.name).toBe('Bob');
  });
});

describe('uniqueBy', () => {
  it('removes duplicates by key', () => {
    const items = [
      { id: 1, email: 'a@test.com' },
      { id: 2, email: 'b@test.com' },
      { id: 3, email: 'a@test.com' }
    ];
    const result = uniqueBy(items, i => i.email);
    expect(result).toHaveLength(2);
    expect(result.map(i => i.id)).toEqual([1, 2]);
  });
});

describe('sortBy', () => {
  it('sorts ascending by default', () => {
    const items = [{ name: 'C' }, { name: 'A' }, { name: 'B' }];
    const result = sortBy(items, i => i.name);
    expect(result.map(i => i.name)).toEqual(['A', 'B', 'C']);
  });

  it('sorts descending', () => {
    const items = [{ value: 1 }, { value: 3 }, { value: 2 }];
    const result = sortBy(items, i => i.value, 'desc');
    expect(result.map(i => i.value)).toEqual([3, 2, 1]);
  });

  it('does not mutate original array', () => {
    const items = [{ value: 3 }, { value: 1 }];
    sortBy(items, i => i.value);
    expect(items[0].value).toBe(3);
  });
});

describe('partition', () => {
  it('splits array by predicate', () => {
    const numbers = [1, 2, 3, 4, 5];
    const [even, odd] = partition(numbers, n => n % 2 === 0);
    expect(even).toEqual([2, 4]);
    expect(odd).toEqual([1, 3, 5]);
  });
});

describe('chunk', () => {
  it('splits array into chunks', () => {
    const items = [1, 2, 3, 4, 5];
    const result = chunk(items, 2);
    expect(result).toEqual([[1, 2], [3, 4], [5]]);
  });

  it('handles empty array', () => {
    expect(chunk([], 3)).toEqual([]);
  });
});

describe('sum', () => {
  it('sums values', () => {
    const items = [{ value: 10 }, { value: 20 }, { value: 30 }];
    expect(sum(items, i => i.value)).toBe(60);
  });

  it('returns 0 for empty array', () => {
    expect(sum([], () => 0)).toBe(0);
  });
});

describe('minBy / maxBy', () => {
  const items = [{ value: 5 }, { value: 2 }, { value: 8 }];

  it('finds minimum', () => {
    expect(minBy(items, i => i.value)?.value).toBe(2);
  });

  it('finds maximum', () => {
    expect(maxBy(items, i => i.value)?.value).toBe(8);
  });

  it('returns undefined for empty array', () => {
    expect(minBy([], () => 0)).toBeUndefined();
  });
});

describe('countBy', () => {
  it('counts matching items', () => {
    const items = [
      { active: true },
      { active: false },
      { active: true }
    ];
    expect(countBy(items, i => i.active)).toBe(2);
  });
});
