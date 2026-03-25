/**
 * Collection utilities for grouping, filtering, and transforming data.
 */

/**
 * Group items by a key extracted from each item.
 *
 * @example
 * const byCategory = groupBy(products, p => p.category);
 * // { "Electronics": [...], "Clothing": [...] }
 */
export function groupBy<T>(items: T[], keyFn: (item: T) => string): Record<string, T[]> {
  const groups: Record<string, T[]> = {};
  for (const item of items) {
    const key = keyFn(item);
    if (!groups[key]) {
      groups[key] = [];
    }
    groups[key].push(item);
  }
  return groups;
}

/**
 * Group items by a key with additional metadata for each group.
 *
 * @example
 * const grouped = groupByWithMeta(
 *   items,
 *   item => item.categoryId,
 *   items => ({ count: items.length, total: sum(items, i => i.value) })
 * );
 */
export function groupByWithMeta<T, M>(
  items: T[],
  keyFn: (item: T) => string,
  metaFn: (items: T[]) => M
): Record<string, { items: T[]; meta: M }> {
  const groups = groupBy(items, keyFn);
  const result: Record<string, { items: T[]; meta: M }> = {};
  for (const [key, groupItems] of Object.entries(groups)) {
    result[key] = {
      items: groupItems,
      meta: metaFn(groupItems)
    };
  }
  return result;
}

/**
 * Create a lookup map from an array.
 *
 * @example
 * const userById = indexBy(users, u => u.id);
 * const user = userById['123'];
 */
export function indexBy<T>(items: T[], keyFn: (item: T) => string): Record<string, T> {
  const map: Record<string, T> = {};
  for (const item of items) {
    map[keyFn(item)] = item;
  }
  return map;
}

/**
 * Unique items by a key function.
 *
 * @example
 * const unique = uniqueBy(items, i => i.email);
 */
export function uniqueBy<T>(items: T[], keyFn: (item: T) => string): T[] {
  const seen = new Set<string>();
  const result: T[] = [];
  for (const item of items) {
    const key = keyFn(item);
    if (!seen.has(key)) {
      seen.add(key);
      result.push(item);
    }
  }
  return result;
}

/**
 * Sort items by a comparable value.
 *
 * @example
 * const sorted = sortBy(users, u => u.name);
 * const sortedDesc = sortBy(users, u => u.createdAt, 'desc');
 */
export function sortBy<T>(
  items: T[],
  valueFn: (item: T) => string | number | Date,
  direction: 'asc' | 'desc' = 'asc'
): T[] {
  const sorted = [...items].sort((a, b) => {
    const aVal = valueFn(a);
    const bVal = valueFn(b);
    if (aVal < bVal) return -1;
    if (aVal > bVal) return 1;
    return 0;
  });
  return direction === 'desc' ? sorted.reverse() : sorted;
}

/**
 * Partition items into two groups based on a predicate.
 *
 * @example
 * const [active, inactive] = partition(users, u => u.isActive);
 */
export function partition<T>(items: T[], predicateFn: (item: T) => boolean): [T[], T[]] {
  const pass: T[] = [];
  const fail: T[] = [];
  for (const item of items) {
    if (predicateFn(item)) {
      pass.push(item);
    } else {
      fail.push(item);
    }
  }
  return [pass, fail];
}

/**
 * Chunk an array into smaller arrays of specified size.
 *
 * @example
 * const pages = chunk(items, 10); // Array of 10-item arrays
 */
export function chunk<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    chunks.push(items.slice(i, i + size));
  }
  return chunks;
}

/**
 * Sum values from items.
 *
 * @example
 * const total = sum(orders, o => o.amount);
 */
export function sum<T>(items: T[], valueFn: (item: T) => number): number {
  return items.reduce((acc, item) => acc + valueFn(item), 0);
}

/**
 * Get min/max from items.
 *
 * @example
 * const oldest = minBy(users, u => new Date(u.createdAt).getTime());
 */
export function minBy<T>(items: T[], valueFn: (item: T) => number): T | undefined {
  if (items.length === 0) return undefined;
  return items.reduce((min, item) => (valueFn(item) < valueFn(min) ? item : min));
}

export function maxBy<T>(items: T[], valueFn: (item: T) => number): T | undefined {
  if (items.length === 0) return undefined;
  return items.reduce((max, item) => (valueFn(item) > valueFn(max) ? item : max));
}

/**
 * Count items matching a predicate.
 *
 * @example
 * const activeCount = countBy(users, u => u.isActive);
 */
export function countBy<T>(items: T[], predicateFn: (item: T) => boolean): number {
  return items.filter(predicateFn).length;
}
