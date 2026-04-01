import { test as base, expect } from '@playwright/test';

/**
 * Extended test fixture that fails on any JavaScript errors or console errors.
 * All tests should use this instead of the default `test` from @playwright/test.
 */
export const test = base.extend<{ pageErrors: string[] }>({
  pageErrors: [async ({ page }, use) => {
    const errors: string[] = [];

    page.on('pageerror', (error) => {
      errors.push(`Page error: ${error.message}`);
    });

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        if (text.includes('favicon') || (text.includes('404') && text.includes('.map'))) {
          return;
        }
        errors.push(`Console error: ${text}`);
      }
    });

    await use(errors);

    if (errors.length > 0) {
      throw new Error(`JavaScript errors detected:\n${errors.join('\n')}`);
    }
  }, { auto: true }],
});

export { expect };
