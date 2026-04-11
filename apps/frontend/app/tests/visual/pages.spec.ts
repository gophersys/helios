import { test, expect } from '@playwright/test';

const pages = [
  { name: 'dashboard', path: '/' },
  { name: 'products', path: '/products' },
  { name: 'builds', path: '/builds' },
  { name: 'validation', path: '/validation' },
  { name: 'validation-queue', path: '/validation/queue' },
  { name: 'manufacturing', path: '/manufacturing' },
  { name: 'manufacturing-sessions', path: '/manufacturing/sessions' },
  { name: 'fixtures', path: '/fixtures' },
  { name: 'history', path: '/history' },
  { name: 'users', path: '/users' },
];

for (const page of pages) {
  test(`visual regression: ${page.name}`, async ({ page: p }) => {
    await p.goto(page.path);
    await p.waitForLoadState('networkidle');
    // Allow any loading spinners or transitions to settle
    await p.waitForTimeout(500);
    await expect(p).toHaveScreenshot(`${page.name}.png`, {
      fullPage: true,
    });
  });
}
