import { test as base, expect } from '@playwright/test';

/**
 * Extended test fixture that fails on any JavaScript errors or console errors.
 * All tests should use this instead of the default `test` from @playwright/test.
 */
export const test = base.extend<{ pageErrors: string[] }>({
  pageErrors: async ({ page }, use) => {
    const errors: string[] = [];

    // Capture uncaught exceptions
    page.on('pageerror', (error) => {
      errors.push(`Page error: ${error.message}`);
    });

    // Capture console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        // Ignore some known noisy errors
        if (
          text.includes('favicon') ||
          text.includes('404') && text.includes('.map')
        ) {
          return;
        }
        errors.push(`Console error: ${text}`);
      }
    });

    await use(errors);

    // After test completes, fail if there were any errors
    if (errors.length > 0) {
      throw new Error(`JavaScript errors detected:\n${errors.join('\n')}`);
    }
  },

  // Auto-use the pageErrors fixture for every test
  page: async ({ page, pageErrors }, use) => {
    await use(page);
    // pageErrors cleanup happens automatically after this
  },
});

export { expect };
